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

    if not os.path.exists(output_path):
        os.mkdir(output_path)

    ln_names = getFileNames(data_path)

    for ln in tqdm(ln_names, desc='languages'):
        ln_path = f'{data_path}/{ln}'
        fnames = getFileNames(ln_path)

        for fn in tqdm(fnames):
            fn_path = f'{ln_path}/{fn}'

            f = open(fn_path)
            df = [json.loads(line, strict=False) for line in f.readlines()]

            redata = []
            for d in df:
                td = []
                content = ""
                for sec in d['sections']:
                    # # if sec['title'] == 'Introduction':
                    # #     continue
                    # content = content + ' ' + sec['content']
                    td.append(sec)

                # if len(content.split(' ')) > 200:
                if len(td) > 1:
                    redata.append({
                        'title': d['title'],
                        'sections': td
                    })

            if not os.path.exists(f'{output_path}/{ln}'):
                os.mkdir(f'{output_path}/{ln}')

            writeFile(redata, f'{output_path}/{ln}/{fn}')

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--data_path')
    parser.add_argument('--output_path')

    args = parser.parse_args()
    main(args)
