#!/usr/bin/env python
# Copyright (C) 2023 Sivan Grünberg <sivan@vitakka.co>
# Vitakka Consulting https://vitakka.co
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
import asyncio
from logging import DEBUG
import openai
import argparse
import autopage

from agit.openai_api import translate_to_git_command, review_patch
from agit.selfdocument import explain
from agit.security import is_destructive
from agit.util import (
    print_explanation,
    print_command,
    print_description,
    gather_output,
    print_review,
)
from agit.os_iface import execute_git_command

# Setup logging
from agit.logger import mylogger


async def main():
    parser = argparse.ArgumentParser(
        description="AGit is an assistant agent that translates natural language to Git commands.",
        epilog="Ensure you have your OpenAI API Key set as an environment variable => OPENAI_API_KEY.",
    )

    parser.add_argument(
        "command",
        type=str,
        help="The natural language commands to be translated to a Git command.",
        nargs="*",  # This makes all arguments to be collected into a list.
    )

    parser.add_argument(
        "--explain",
        action="store_true",
        help="Provides an extended explanation and usage examples of AGit.",
    )

    parser.add_argument("--debug", action="store_true", help="Debug prompt template.")

    parser.add_argument(
        "--review",
        action="store_true",
        help="Review current un-staged changes against latest revision.",
    )

    args = parser.parse_args()

    if args.debug:
        mylogger.setLevel(DEBUG)

    if args.review:
        cmd = "git diff"
        mylogger.debug("Starting review...")
        diff_output = gather_output(cmd=cmd)
        content = await review_patch(
            diff_content=diff_output, instruct_review=args.command
        )
        with autopage.AutoPager(
            allow_color=True, pager_command=autopage.command.PlatformPager()
        ) as out_stream0:
            print_review(feedback=content, out_stream=out_stream0)
        return

    if args.explain and not args.command:
        explain()
        return

    if not args.command:
        parser.print_help()
        return

    if not openai.api_key:
        print("OpenAI API key was not set, please set it before using AGit.")
        return

    natural_language = " ".join(args.command)
    if args.debug:
        mylogger.debug(f"natural language query: {natural_language}")

    git_command = await translate_to_git_command(natural_language, args.explain)

    if args.debug:
        mylogger.debug(f"Model Response: {git_command}")

    with autopage.AutoPager(
        allow_color=True, pager_command=autopage.command.PlatformPager()
    ) as out_stream:
        print_command(git_command["command"], out_stream)
        print_description(git_command["description"], out_stream)
        out_stream.flush()

        if args.explain:
            print_explanation(git_command["explain"], out_stream)
        out_stream.flush()

        is_destructive_result = is_destructive(git_command["command"])
        if not is_destructive_result[0]:
            stdout = execute_git_command(git_command["command"].split())
            out_stream.write(stdout)
            return

    if is_destructive_result[0]:
        print("Warning: This seems to be a destructive command")
        print(f"Reason: {is_destructive_result[1]} \n")
        proceed = input("Do you wish to continue? (Y/N):")
        if proceed.strip().lower() != "y":
            print("Execution stopped.")
            return
        stdout = execute_git_command(git_command["command"].split())
        with autopage.AutoPager(
            allow_color=True, pager_command=autopage.command.PlatformPager()
        ) as out_stream2:
            out_stream2.write(stdout)
            out_stream2.flush()


def async_main():
    asyncio.run(main())


if __name__ == "__main__":
    async_main()