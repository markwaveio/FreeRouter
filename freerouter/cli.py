from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

from pydantic import BaseModel, ConfigDict

from freerouter.docs import read_env_file, signup_url, sync
from freerouter.errors import MissingMasterKeyError, RegistryError
from freerouter.gateway import PROBE_TAG, Gateway
from freerouter.refresh import Settings, run_cycle
from freerouter.registry import credentials_for, load_providers
from freerouter.state import HealthStatus, clear_quarantine, load_state, save_state, utcnow
from freerouter.watch import refresh_catalog

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from freerouter.refresh import CycleReport

LOGGER: Final = logging.getLogger("freerouter")
DEFAULT_CHANGE_LINES: Final = 30
DEFAULT_CALL_LINES: Final = 20
PROVIDERS_ENV: Final = "FREEROUTER_PROVIDERS_DIR"


class CallRecord(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    startTime: str = ""  # noqa: N815 - LiteLLM's field name
    status: str = "unknown"
    model_group: str | None = None
    model: str | None = None
    model_id: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    request_duration_ms: float | None = None
    spend: float = 0.0
    request_tags: tuple[str, ...] = ()

    @property
    def is_probe(self) -> bool:
        """Report whether this request was FreeRouter's own health probe."""
        return PROBE_TAG in self.request_tags


class ChangeRecord(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    ts: str
    event: str
    provider: str
    detail: str
    model: str | None = None

USAGE: Final = """FreeRouter 免费模型池维护工具

  freerouter refresh   跑一轮发现 + 探测 + 热更新，然后退出
  freerouter daemon    常驻循环，按 FREEROUTER_REFRESH_INTERVAL 定期刷新
  freerouter report    打印当前模型池状态（只读本地 state，不联网）
  freerouter changes   打印最近的模型池变更记录
  freerouter recheck [平台]  修好根因后清掉隔离与退避，让下一轮重新探测
  freerouter calls     打印最近的调用记录（请求名 → 实际命中哪个模型）
                       加 --no-probe 只看你自己的调用，不看刷新器的探测
  freerouter keys      列出所有平台：哪些已配置、没配的去哪注册领 Key
  freerouter docs      把平台表格同步进 README.md 和 .env.example
  freerouter watch     刷新 catalog/ 快照与文档，供 CI 开 PR 使用
"""


def _configure_logging() -> None:
    """Send structured logs to stderr so `docker compose logs` stays readable."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s freerouter: %(message)s",
        stream=sys.stderr,
    )


def _log_report(report: CycleReport) -> None:
    """Log one cycle's summary, events and errors."""
    LOGGER.info("cycle complete: %s", report.summary())
    for event in report.events:
        LOGGER.info("change %s", event.as_text())
    for error in report.errors:
        LOGGER.error("cycle error: %s", error)


def cmd_refresh(_: Sequence[str]) -> int:
    """Run exactly one refresh cycle."""
    settings = Settings.from_env()
    gateway = Gateway(base_url=settings.gateway_url, master_key=settings.master_key)
    if not gateway.wait_ready(settings.ready_timeout):
        LOGGER.error("gateway %s did not become ready", settings.gateway_url)
        return 1
    report = run_cycle(settings)
    _log_report(report)
    return 1 if report.errors else 0


def cmd_daemon(_: Sequence[str]) -> int:
    """Refresh on a fixed interval until the container stops."""
    settings = Settings.from_env()
    gateway = Gateway(base_url=settings.gateway_url, master_key=settings.master_key)
    LOGGER.info(
        "refresher started: gateway=%s interval=%.0fs providers=%s",
        settings.gateway_url,
        settings.interval,
        settings.providers_dir,
    )
    if not gateway.wait_ready(settings.ready_timeout):
        LOGGER.warning("gateway not ready yet; continuing and retrying each cycle")

    while True:
        try:
            _log_report(run_cycle(settings))
        except (RegistryError, OSError):
            LOGGER.exception("refresh cycle failed")
        time.sleep(settings.interval)


def _state_dir(env: Mapping[str, str]) -> Path:
    """Resolve the state directory without requiring gateway credentials."""
    return Path(env.get("FREEROUTER_STATE_DIR", "/app/state"))


def cmd_report(_: Sequence[str]) -> int:
    """Print the current pool state from disk."""
    state = load_state(_state_dir(os.environ) / "health.json")
    if not state.models:
        print("模型池为空：refresher 还没跑过，或者所有平台都缺少 API Key。")  # noqa: T201
        return 0

    print(f"更新时间: {state.updated_at}")  # noqa: T201
    for provider in sorted({health.provider for health in state.models.values()}):
        entries = sorted(
            (h for h in state.models.values() if h.provider == provider),
            key=lambda item: item.model_id,
        )
        healthy = sum(1 for h in entries if h.status is HealthStatus.HEALTHY)
        print(f"\n{provider}  ({healthy}/{len(entries)} 可用)")  # noqa: T201
        for health in entries:
            mark = {"healthy": "OK ", "quarantined": "OUT", "unknown": "?  "}[health.status.value]
            reason = f"  {health.last_error}" if health.last_error else ""
            print(f"  {mark} {health.model_id}{reason}")  # noqa: T201
    return 0


def cmd_changes(argv: Sequence[str]) -> int:
    """Print the most recent pool changes from the local changelog."""
    limit = int(argv[0]) if argv and argv[0].isdigit() else DEFAULT_CHANGE_LINES
    path = _state_dir(os.environ) / "changelog.jsonl"
    if not path.exists():
        print(f"还没有变更记录：{path}")  # noqa: T201
        return 0

    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines[-limit:]:
        if not line.strip():
            continue
        record = ChangeRecord.model_validate_json(line)
        target = f"{record.provider}/{record.model}" if record.model else record.provider
        print(f"{record.ts[:19]}  {record.event:<16} {target}")  # noqa: T201
        print(f"    {record.detail}")  # noqa: T201
    return 0


def cmd_calls(argv: Sequence[str]) -> int:
    """Print recent requests, showing which deployment each alias actually hit."""
    limit = int(argv[0]) if argv and argv[0].isdigit() else DEFAULT_CALL_LINES
    settings = Settings.from_env()
    gateway = Gateway(base_url=settings.gateway_url, master_key=settings.master_key)
    entries = [CallRecord.model_validate(item) for item in gateway.spend_logs()]
    if not entries:
        print("还没有调用记录。")  # noqa: T201
        return 0

    if "--no-probe" in argv:
        entries = [entry for entry in entries if not entry.is_probe]
    entries.sort(key=lambda item: item.startTime)

    print("时间      结果  耗时      tokens   来源")  # noqa: T201
    for entry in entries[-limit:]:
        took = f"{entry.request_duration_ms:.0f}ms" if entry.request_duration_ms else "-"
        mark = "OK  " if entry.status == "success" else "FAIL"
        source = "探测" if entry.is_probe else "调用"
        tokens = f"{entry.prompt_tokens}+{entry.completion_tokens}"
        print(  # noqa: T201
            f"{entry.startTime[11:19]}  {mark}  {took:<9} {tokens:<8} {source}"
        )
        print(f"          {entry.model_group or '?'}  →  {entry.model or '?'}")  # noqa: T201
    return 0


def cmd_recheck(argv: Sequence[str]) -> int:
    """Clear quarantine and backoff so the next cycle re-verifies those models."""
    provider_id = argv[0] if argv else None
    path = _state_dir(os.environ) / "health.json"
    state = load_state(path)
    if not state.models:
        print("模型池为空，没有需要重检的。")  # noqa: T201
        return 0

    updated, reset = clear_quarantine(state, provider_id)
    if reset == 0:
        print("没有处于隔离或失败计数中的模型。")  # noqa: T201
        return 0

    save_state(updated, path, utcnow())
    scope = provider_id or "全部平台"
    print(f"已清除 {scope} 的 {reset} 个模型的隔离状态与退避计时。")  # noqa: T201
    print("跑 make refresh 立即重新探测（受各平台 probe.max_per_cycle 上限约束）。")  # noqa: T201
    return 0


def cmd_keys(argv: Sequence[str]) -> int:
    """List every platform, marking which are configured and where to get the rest."""
    root = Path(argv[0]) if argv else Path()
    providers_dir = root / "providers"
    if not providers_dir.is_dir():
        providers_dir = Path(os.environ.get(PROVIDERS_ENV, "providers"))
    providers = sorted(load_providers(providers_dir), key=lambda item: item.provider_id)
    configured = {**os.environ, **read_env_file(root / ".env")}

    ready: list[str] = []
    missing: list[tuple[str, str, str | None, bool]] = []
    for provider in providers:
        if not provider.routable or not provider.credential:
            continue
        if credentials_for(provider, configured):
            ready.append(f"{provider.name_zh} ({provider.provider_id})")
        else:
            missing.append(
                (
                    provider.name_zh,
                    provider.credential,
                    signup_url(provider),
                    bool(provider.referral_url),
                )
            )

    print(f"已配置 {len(ready)} 个平台：")  # noqa: T201
    for name in ready:
        print(f"  OK  {name}")  # noqa: T201
    if not ready:
        print("  （一个都没配，填任意一个下面的 Key 就能跑）")  # noqa: T201

    print(f"\n还没配置 {len(missing)} 个，去这里领 Key：")  # noqa: T201
    for name, variable, url, invited in missing:
        print(f"  {name}")  # noqa: T201
        print(f"    .env 里填 {variable}=")  # noqa: T201
        if url:
            mark = "  (邀请链接，双方都有奖励)" if invited else ""
            print(f"    注册: {url}{mark}")  # noqa: T201
    print("\n填完运行 make refresh，新平台立刻接入，不用重启。")  # noqa: T201
    return 0


def cmd_docs(argv: Sequence[str]) -> int:
    """Regenerate the platform tables in README.md and .env.example."""
    root = Path(argv[0]) if argv else Path()
    updated = sync(root / "providers", root / "README.md", root / ".env.example")
    for path in updated:
        print(f"updated {path}")  # noqa: T201
    if not updated:
        print("README.md 和 .env.example 已经是最新的。")  # noqa: T201
    return 0


def cmd_watch(argv: Sequence[str]) -> int:
    """Refresh the committed catalog snapshot and documentation."""
    root = Path(argv[0]) if argv else Path()
    providers_dir = root / "providers" if (root / "providers").is_dir() else Path("providers")
    # Locally the project's `.env` is not exported, so read it directly; in CI the
    # credentials arrive as real environment variables and this is simply empty.
    env = {**os.environ, **read_env_file(root / ".env")}
    changes = refresh_catalog(providers_dir, env=env)
    for line in changes:
        print(line)  # noqa: T201
    print("CHANGED" if changes else "UNCHANGED")  # noqa: T201
    return 0


COMMANDS: Final[Mapping[str, Callable[[Sequence[str]], int]]] = {
    "refresh": cmd_refresh,
    "daemon": cmd_daemon,
    "report": cmd_report,
    "changes": cmd_changes,
    "recheck": cmd_recheck,
    "keys": cmd_keys,
    "docs": cmd_docs,
    "calls": cmd_calls,
    "watch": cmd_watch,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch one FreeRouter subcommand."""
    _configure_logging()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(USAGE)  # noqa: T201
        return 0
    handler = COMMANDS.get(args[0])
    if handler is None:
        print(f"未知命令: {args[0]}\n\n{USAGE}", file=sys.stderr)  # noqa: T201
        return 2
    try:
        return handler(args[1:])
    except MissingMasterKeyError as error:
        LOGGER.error("%s", error)  # noqa: TRY400 - the traceback adds nothing here
        return 1
    except RegistryError:
        LOGGER.exception("provider registry is invalid")
        return 1
    except KeyboardInterrupt:
        return 130
