#!/usr/bin/env python
"""Read-only smoke checks for the legacy dc_api module.

This script intentionally avoids write_document, write_comment, modify, and
delete paths. It is safe to run while restoring the bot because it only reads
public gallery pages, one document, and one comment endpoint.
"""

import argparse
import asyncio
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dc_api


async def collect_board(api, board_id, limit):
    posts = []
    async for index in api.board(board_id=board_id, num=limit):
        posts.append(index)
    return posts


async def collect_comments(api, board_id, document_id, limit):
    comments = []
    async for comment in api.comments(board_id=board_id, document_id=document_id, num=limit):
        comments.append(comment)
    return comments


async def run_smoke(board_id, limit, comment_limit):
    print(f"dc_api path: {dc_api.__file__}")
    print(f"board_id: {board_id}")
    print(f"board limit: {limit}")

    async with dc_api.API() as api:
        posts = await collect_board(api, board_id, limit)
        print(f"[board] fetched {len(posts)} posts")
        if not posts:
            raise AssertionError("board() returned no posts")

        for i, post in enumerate(posts, start=1):
            print(
                f"[board:{i}] id={post.id} comments={post.comment_count} "
                f"author={post.author!r} title={post.title!r}"
            )

        first = posts[0]
        doc = await api.document(board_id=board_id, document_id=first.id)
        if doc is None:
            raise AssertionError(f"document() returned None for {board_id}/{first.id}")

        print(
            f"[document] id={doc.id} author={doc.author!r} "
            f"title={doc.title!r} contents_len={len(doc.contents or '')}"
        )
        if not doc.title:
            raise AssertionError("document() returned an empty title")

        comment_target = next((post for post in posts if post.comment_count > 0), first)
        comments = await collect_comments(api, board_id, comment_target.id, comment_limit)
        print(
            f"[comments] doc_id={comment_target.id} expected_count={comment_target.comment_count} "
            f"fetched={len(comments)}"
        )
        for i, comment in enumerate(comments[:3], start=1):
            print(
                f"[comments:{i}] id={comment.id} reply={comment.is_reply} "
                f"author={comment.author!r} contents={comment.contents!r}"
            )

    print("smoke result: PASS")


async def main():
    parser = argparse.ArgumentParser(description="Run read-only dc_api smoke checks.")
    parser.add_argument("--board-id", default="jazz")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--comment-limit", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    try:
        await asyncio.wait_for(
            run_smoke(args.board_id, args.limit, args.comment_limit),
            timeout=args.timeout,
        )
    except Exception as exc:
        print(f"smoke result: FAIL ({type(exc).__name__}: {exc})")
        traceback.print_exc()
        raise SystemExit(1) from exc


if __name__ == "__main__":
    asyncio.run(main())
