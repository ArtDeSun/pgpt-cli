from __future__ import annotations

import argparse
import json

from pgpt.config import CONFIG, get_project, save_user_project
from pgpt.maintenance import (
    ingest,
    ingest_directory,
    models,
    resolve_knowledge_directory,
    serve as serve_private_gpt,
    status,
    sync,
)
from pgpt.retrieval.project import has_symbol_hit, select_user_project
from pgpt.retrieval.web_usage import usage_snapshot
from pgpt.routing.router import resolve_route
from pgpt.runtime.pipeline import run
from pgpt.server import serve as serve_local
from pgpt.skills import create_skill, list_skills, skill_history
from pgpt.storage import chats


def _web(value: str | None) -> str | None:
    if value in {None, "auto"}:
        return None
    return {"on": "lookup", "lookup": "lookup", "research": "research", "off": "off"}[
        value
    ]


def cmd_ask(args: argparse.Namespace) -> None:
    prompt = args.prompt or input("You > ")
    result = run(
        prompt,
        project_name=args.project,
        web_override=_web(args.web),
        project_override=args.context,
        template_override=args.template,
        model_override=args.model,
        deep_override=args.deep,
        history=skill_history(None, args.skill),
    )
    print(f"[saved] {result.response_path}")


def _validation_project(prompt: str, args: argparse.Namespace) -> str | None:
    if args.project:
        return get_project(args.project)[0]
    if args.context is False:
        return None
    selected = select_user_project(prompt)
    if args.context is True and selected is None:
        raise ValueError("Project context was forced but no project was selected")
    return selected


def cmd_validate(args: argparse.Namespace) -> None:
    prompt = args.prompt or input("You > ")
    project_name = _validation_project(prompt, args)
    symbol = bool(project_name and has_symbol_hit(prompt, project_name))
    decision = resolve_route(
        prompt,
        project_name=project_name or "",
        web_override=_web(args.web),
        project_override=args.context,
        template_override=args.template,
        model_override=args.model,
        deep_override=args.deep,
        symbol_hit=symbol,
    )
    payload = {**decision.__dict__, "selected_project": project_name}
    print(json.dumps(payload, indent=2))


def cmd_chat_new(args: argparse.Namespace) -> None:
    project_name = get_project(args.project)[0] if args.project else None
    slug = chats.create(args.title, project_name)
    print(f"Created and selected chat: {slug}")


def cmd_chat_list(_args: argparse.Namespace) -> None:
    current = chats.current()
    for slug, data in chats.list_chats():
        marker = "*" if slug == current else " "
        project = data.get("project") or "auto"
        print(f"{marker} {slug:32} {project:16} {data.get('title','')}")


def cmd_skills(_args: argparse.Namespace) -> None:
    names = list_skills()
    if not names:
        print("No skills found.")
        return
    for name in names:
        print(name)


def cmd_skill_new(args: argparse.Namespace) -> None:
    print(create_skill(args.name))


def cmd_web_usage(_args: argparse.Namespace) -> None:
    print(json.dumps(usage_snapshot(), indent=2))


def cmd_context_add(args: argparse.Namespace) -> None:
    root = resolve_knowledge_directory(args.path)
    entry = save_user_project(
        args.name,
        str(root),
        collection=args.collection,
    )
    print(f"Registered context: {args.name.strip().casefold()} -> {entry['source_dir']}")


def cmd_knowledge_add(args: argparse.Namespace) -> None:
    def emit(line: str) -> None:
        print(line)

    code = ingest_directory(
        args.path,
        project_name=args.name,
        collection=args.collection,
        ignored=list(args.ignore or []),
        on_line=emit,
    )
    if code != 0:
        raise RuntimeError(f"PrivateGPT ingestion failed with exit code {code}")
    print(f"Added knowledge project: {args.name.strip().casefold()}")


def cmd_server(args: argparse.Namespace) -> None:
    serve_local(host=args.host, port=args.port, allow_remote=args.allow_remote)


def cmd_chat(args: argparse.Namespace) -> None:
    slug = args.slug or chats.current()
    if not slug:
        title = input("New chat title > ").strip() or "New chat"
        project_name = get_project(args.project)[0] if args.project else None
        slug = chats.create(title, project_name)
    chats.set_current(slug)
    data = chats.load(slug)
    print(f"Chat: {data['title']} [{slug}]")
    print(
        "Commands: /quit /new TITLE /web auto|on|off|lookup|research "
        "/context auto|on|off /deep auto|on|off /skill off|NAME\n"
    )
    web_override = _web(args.web)
    context_override = args.context
    deep_override = args.deep
    skill_override = args.skill
    while True:
        try:
            prompt = input("You > ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not prompt.strip():
            continue
        if prompt.startswith("/"):
            command, _, rest = prompt.partition(" ")
            rest = rest.strip()
            if command in {"/quit", "/exit"}:
                break
            if command == "/new" and rest:
                slug = chats.create(rest, data.get("project"))
                data = chats.load(slug)
                print(f"Switched to {slug}")
                continue
            if command == "/web":
                if rest not in {"auto", "on", "off", "lookup", "research"}:
                    print("Usage: /web auto|on|off|lookup|research")
                else:
                    web_override = _web(rest)
                    print(f"Web: {rest}")
                continue
            if command == "/context":
                if rest not in {"auto", "on", "off"}:
                    print("Usage: /context auto|on|off")
                else:
                    context_override = None if rest == "auto" else rest == "on"
                    print(f"Context: {rest}")
                continue
            if command == "/deep":
                if rest not in {"auto", "on", "off"}:
                    print("Usage: /deep auto|on|off")
                else:
                    deep_override = None if rest == "auto" else rest == "on"
                    print(f"Deep: {rest}")
                continue
            if command == "/skill":
                if rest in {"", "off"}:
                    skill_override = None
                    print("Skill: off")
                elif rest in list_skills():
                    skill_override = rest
                    print(f"Skill: {rest}")
                else:
                    print("Unknown skill. Run `pgpt skills` to list available skills.")
                continue
            print("Unknown command")
            continue
        history = data.get("messages", [])
        result = run(
            prompt,
            project_name=data.get("project"),
            web_override=web_override,
            project_override=context_override,
            template_override=args.template,
            model_override=args.model,
            deep_override=deep_override,
            history=skill_history(history, skill_override),
        )
        data["messages"] = [
            *history,
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": result.answer},
        ]
        chats.save(slug, data)
        print(f"[saved] {result.response_path}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pgpt")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(func=lambda _a: status())
    sub.add_parser("models").set_defaults(func=lambda _a: models())
    sub.add_parser("skills").set_defaults(func=cmd_skills)
    sub.add_parser("web-usage").set_defaults(func=cmd_web_usage)

    skill_new = sub.add_parser("skill-new")
    skill_new.add_argument("name")
    skill_new.set_defaults(func=cmd_skill_new)

    context_add = sub.add_parser(
        "context-add",
        help="Register a local folder for direct project/context retrieval",
    )
    context_add.add_argument("path")
    context_add.add_argument("--name", required=True)
    context_add.add_argument("--collection")
    context_add.set_defaults(func=cmd_context_add)

    knowledge_add = sub.add_parser(
        "knowledge-add",
        help="Ingest and register an arbitrary local folder through PrivateGPT",
    )
    knowledge_add.add_argument("path")
    knowledge_add.add_argument("--name", required=True)
    knowledge_add.add_argument("--collection")
    knowledge_add.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Basename PrivateGPT should ignore; may be repeated",
    )
    knowledge_add.set_defaults(func=cmd_knowledge_add)

    private_serve = sub.add_parser("serve")
    private_serve.set_defaults(func=lambda _a: serve_private_gpt())

    local_server = sub.add_parser("server")
    local_server.add_argument("--host")
    local_server.add_argument("--port", type=int)
    local_server.add_argument("--allow-remote", action="store_true")
    local_server.set_defaults(func=cmd_server)

    p = sub.add_parser("sync")
    p.add_argument("--project")
    p.set_defaults(func=lambda a: sync(a.project))

    p = sub.add_parser("ingest")
    p.add_argument("--project")
    p.add_argument("--watch", action="store_true")
    p.set_defaults(func=lambda a: ingest(a.project, a.watch))

    def add_common_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--project")
        p.add_argument(
            "-t",
            "--template",
            choices=[
                "general",
                "explain-code",
                "debug",
                "implement",
                "architecture",
                "research",
            ],
        )
        p.add_argument("-m", "--model")
        p.add_argument(
            "--web",
            choices=["auto", "on", "off", "lookup", "research"],
            default="auto",
        )
        group = p.add_mutually_exclusive_group()
        group.add_argument("--context", dest="context", action="store_true")
        group.add_argument("--no-context", dest="context", action="store_false")
        p.set_defaults(context=None)
        deep = p.add_mutually_exclusive_group()
        deep.add_argument("--deep", dest="deep", action="store_true")
        deep.add_argument("--no-deep", dest="deep", action="store_false")
        p.set_defaults(deep=None)

    p = sub.add_parser("ask")
    p.add_argument("prompt", nargs="?")
    p.add_argument("--skill")
    add_common_args(p)
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("validate")
    p.add_argument("prompt", nargs="?")
    add_common_args(p)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("chat-new")
    p.add_argument("title")
    p.add_argument("--project")
    p.set_defaults(func=cmd_chat_new)

    p = sub.add_parser("chat-list")
    p.set_defaults(func=cmd_chat_list)

    p = sub.add_parser("chat")
    p.add_argument("slug", nargs="?")
    p.add_argument("--skill")
    add_common_args(p)
    p.set_defaults(func=cmd_chat)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
