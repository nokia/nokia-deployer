#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).

import argparse

import requests


def main():
    parser = define_parser()
    args = parser.parse_args()
    send_payload(args.repository, args.branch, args.newrev, args.hostname)
    print("Sucessfully sent payload to {}".format(args.hostname))


def send_payload(repo_name, branch, newrev, hostname):
    url = "http://{}/notify/github".format(hostname)
    data = {
        'repository': {
            'full_name': repo_name
        },
        'after': newrev,
        'ref': 'refs/heads/{}'.format(branch)
    }
    resp = requests.post(url, json=data)
    resp.raise_for_status()


def define_parser():
    parser = argparse.ArgumentParser(description="Mimic a part of the payload Github sends us when someone pushes to one of our Github repos.")
    parser.add_argument('--repository', default='apiv2')
    parser.add_argument('--branch', default='master')
    parser.add_argument('--newrev', default='1a06b106c37235ef79b12ca8a75bbfc851922488')
    parser.add_argument('hostname')
    return parser


if __name__ == "__main__":
    main()
