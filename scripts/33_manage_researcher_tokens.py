from __future__ import annotations

import argparse
from pathlib import Path

from rq_platform.auth import (
    ResearcherToken,
    generate_token,
    hash_token,
    load_researcher_tokens,
    save_researcher_tokens,
)
from rq_platform.settings import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage researcher API tokens.")
    parser.add_argument("--config", default=str(settings.researcher_tokens_path_obj))
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--researcher-id", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--note", default="")

    subparsers.add_parser("list")

    disable = subparsers.add_parser("disable")
    disable.add_argument("--researcher-id", required=True)

    enable = subparsers.add_parser("enable")
    enable.add_argument("--researcher-id", required=True)

    args = parser.parse_args()
    path = Path(args.config)
    tokens = load_researcher_tokens(path)

    if args.command == "create":
        if any(item.researcher_id == args.researcher_id for item in tokens):
            raise SystemExit(f"researcher_id already exists: {args.researcher_id}")
        plain_token = generate_token()
        tokens.append(
            ResearcherToken(
                researcher_id=args.researcher_id,
                name=args.name,
                token_hash=hash_token(plain_token),
                enabled=True,
                note=args.note,
            )
        )
        save_researcher_tokens(tokens, path)
        print(f"researcher_id={args.researcher_id}")
        print(f"name={args.name}")
        print(f"token={plain_token}")
        print(f"config={path}")
        print("token is shown once; store it securely")
        return 0

    if args.command == "list":
        print("researcher_id,name,enabled,note")
        for item in tokens:
            print(f"{item.researcher_id},{item.name},{item.enabled},{item.note}")
        return 0

    if args.command in {"disable", "enable"}:
        enabled = args.command == "enable"
        updated = []
        found = False
        for item in tokens:
            if item.researcher_id == args.researcher_id:
                updated.append(
                    ResearcherToken(
                        researcher_id=item.researcher_id,
                        name=item.name,
                        token_hash=item.token_hash,
                        enabled=enabled,
                        note=item.note,
                    )
                )
                found = True
            else:
                updated.append(item)
        if not found:
            raise SystemExit(f"researcher_id not found: {args.researcher_id}")
        save_researcher_tokens(updated, path)
        print(f"researcher_id={args.researcher_id}")
        print(f"enabled={enabled}")
        print(f"config={path}")
        return 0

    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
