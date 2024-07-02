import os
import json
import argparse
import evaluate
import pandas as pd

from tqdm import tqdm
from rouge import Rouge
from icecream import ic
from collections import defaultdict


def getFileNames(path):
    fnames = [f for f in os.listdir(path)]
    return fnames


def writeFile(data, path):
    f = open(path, 'w')
    for dic in data:
        f.write(json.dumps(dic, ensure_ascii=False))
        f.write('\n')


def main(args):

    data_path = args.data_path
    output_path = args.output_path
    word_limit = args.word_limit

    if not os.path.exists(output_path):
        os.mkdir(output_path)

    ln_names = getFileNames(data_path)

    for ln in tqdm(ln_names, desc='split'):
        ln_path = f'{data_path}/{ln}'

        f = open(ln_path)
        df = [json.loads(line, strict=False) for line in f.readlines()]

        redata = []
        for d in df:
            content = ""
            for sec in d['article']['sections']:
                content = content + ' ' + sec['content']

            if len(content.split(' ')) > word_limit:
                redata.append(d)

        writeFile(redata, f'{output_path}/{ln}')

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--data_path')
    parser.add_argument('--output_path')
    parser.add_argument('--word_limit', type=int)

    args = parser.parse_args()
    main(args)
