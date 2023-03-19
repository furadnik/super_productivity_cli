"""CLI for Yearly Hue."""
from argparse import ArgumentParser
from typing import Iterable

from .client import SupProd, Task

supprod = SupProd.from_config()


def get_list_tasks(args, supprod: SupProd) -> Iterable[Task]:
    """List tasks by arg values."""
    gen = supprod
    if args.project_title:
        gen = supprod.get_project_by_name(args.project_title)  # type: ignore

    return reversed(gen.todays_tasks if args.today else gen.tasks)


def default_task_params(parser: ArgumentParser) -> None:
    """Add default task params."""
    parser.add_argument("--project-title", type=str, help="project title.")
    parser.add_argument("--today", default=False, action="store_true",
                        help="is it today.")


ap = ArgumentParser()
sp = ap.add_subparsers()

todo_list = sp.add_parser("list", aliases=["l", "get", "g"], help="list tasks.")
default_task_params(todo_list)
todo_list.set_defaults(func=lambda args, supprod: [print(x.title) for x in
                                                   get_list_tasks(args, supprod)])


def urls_list_f(args, supprod: SupProd) -> None:
    """Print urls w tasks."""
    for task in get_list_tasks(args, supprod):
        for attachment in task.attachments:
            if attachment.attachment_type == "LINK":
                print(attachment.path, task.title, sep="\t")


urls_list = sp.add_parser("urls", help="list tasks w urls.")
default_task_params(urls_list)
urls_list.set_defaults(func=urls_list_f)

args = ap.parse_args()

args.func(args, supprod)
