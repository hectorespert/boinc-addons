import argparse
import json

parser = argparse.ArgumentParser(prog='operator')

parser.add_argument('options', type=argparse.FileType('r', encoding='UTF-8'))

args = parser.parse_args()

options = json.load(args.options)

print(options)