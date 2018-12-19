from argparse import ArgumentParser


def set_args(args):
    parser = ArgumentParser()
    map(lambda arg: parser.add_argument(arg[0], **arg[1]), args)
    return parser.parse_args()
