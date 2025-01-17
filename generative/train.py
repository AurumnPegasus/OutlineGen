from model.model import Summarizer
from model.reward_model import Summarizer as R_Summarizer
from model.dataloader import DataModule
from icecream import ic
from collections import defaultdict

import pytorch_lightning as pl
# from pytorch_lightning.loggers import WandbLogger
from pytorch_lightning.callbacks import ModelCheckpoint
from pytorch_lightning.plugins import DDPPlugin

import os
import sys
import glob
import time
import torch
import argparse
import pandas as pd
# os.environ["WANDB_SILENT"] = "True"

def getMatrices(path):
    LANGS = ['en', 'hi', 'bn', 'te', 'ta', 'pa', 'or', 'ml', 'kn', 'mr']
    DOMS = ['animals', 'companies', 'books', 'politicians', 'sportsman', 'writers', 'cities', 'films']

    fsa_dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(float))))

    for ln in LANGS:
        for dm in DOMS:
            current_path = f'{path}/{ln}_{dm}.csv'
            df = pd.read_csv(current_path)
            cols = df['Unnamed: 0']
            dic = df.to_dict()

            for key in dic.keys():
                for vals in dic[key].keys():
                    if pd.isna(dic[key][vals]):
                        pass
                    else:
                        fsa_dict[ln][dm][key][cols[vals]] = dic[key][vals]

    return fsa_dict



def main(args):

    train_path = args.train_path
    val_path = args.val_path
    test_path = args.test_path

    tokenizer_name_or_path = args.tokenizer
    model_name_or_path = args.model
    is_mt5 = args.is_mt5
    lr = args.learning_rate

    if args.config is not None:
        config = args.config
    else:
        config = model_name_or_path

    if not os.path.exists(args.prediction_path):
        os.system(f'mkdir -p {args.prediction_path}')

    n_gpus = args.n_gpus
    strategy = args.strategy
    EXP_NAME = args.exp_name
    save_dir = args.save_dir
    target_lang = args.target_lang
    num_epochs = args.num_epochs
    train_batch_size = args.train_batch_size
    val_batch_size = args.val_batch_size
    test_batch_size = args.test_batch_size
    max_source_length = args.max_source_length
    max_target_length = args.max_target_length
    prediction_path = args.prediction_path
    reward = args.reward
    fsa_path = args.fsa_path
    beam_size = args.beam_size
    wb = args.wandb
    old_checkpoint = args.old_checkpoint

    if wb:
        from pytorch_lightning.loggers import WandbLogger
        os.environ["WANDB_SILENT"] = "True"


    ic("Got all args")

    dm_hparams = dict(
        train_path=train_path,
        val_path=val_path,
        test_path=test_path,
        tokenizer_name_or_path=tokenizer_name_or_path,
        is_mt5=is_mt5,
        max_source_length=max_source_length,
        max_target_length=max_target_length,
        train_batch_size=train_batch_size,
        val_batch_size=val_batch_size,
        test_batch_size=test_batch_size,
        target_lang=target_lang
    )
    dm = DataModule(**dm_hparams)

    fsa_dict = getMatrices(fsa_path)

    ic("Created data module")

    model_hparams = dict(
        learning_rate=lr,
        model_name_or_path=model_name_or_path,
        config = config,
        is_mt5=is_mt5,
        eval_beams=3,
        tgt_max_seq_len=max_target_length,
        tokenizer=dm.tokenizer,
        target_lang=target_lang,
        prediction_path=prediction_path,
        old_checkpoint=old_checkpoint,
        beam_size=beam_size
    )

    if reward == 0:
        model = Summarizer(**model_hparams)
    else:
        model = R_Summarizer(fsa_dict=fsa_dict, reward_val=reward,**model_hparams)

    ic("Created model")

    if args.sanity_run=='yes':
        log_model = False
        limit_train_batches = 4
        limit_val_batches = 4
        limit_test_batches = 4
    else:
        log_model = True
        limit_train_batches = 1.0
        limit_val_batches = 1.0
        limit_test_batches = 1.0

    checkpoint_callback = ModelCheckpoint(monitor='val_loss', mode='min',
                                         dirpath=os.path.join(save_dir+EXP_NAME, 'lightning-checkpoints'),
                                        filename='{epoch}-{step}',
                                        save_top_k=1,
                                        verbose=True,
                                        save_last=False,
                                        save_weights_only=False)

    if wb:
        trainer_hparams = dict(
            gpus=n_gpus,
            strategy=strategy,
            max_epochs=num_epochs,
            num_sanity_val_steps=3,
            logger=WandbLogger(name=model_name_or_path.split('/')[-1], save_dir=save_dir+EXP_NAME, project=EXP_NAME, log_model=False),
            check_val_every_n_epoch=1,
            val_check_interval=1.0,
            enable_checkpointing=True,
            callbacks=[checkpoint_callback],
            limit_train_batches=limit_train_batches,
            limit_val_batches=limit_val_batches,
            limit_test_batches=limit_test_batches
        )
    else:
        trainer_hparams = dict(
            gpus=n_gpus,
            strategy=strategy,
            max_epochs=num_epochs,
            num_sanity_val_steps=3,
            # logger=WandbLogger(name=model_name_or_path.split('/')[-1], save_dir=save_dir+EXP_NAME, project=EXP_NAME, log_model=False),
            check_val_every_n_epoch=1,
            val_check_interval=1.0,
            enable_checkpointing=True,
            callbacks=[checkpoint_callback],
            limit_train_batches=limit_train_batches,
            limit_val_batches=limit_val_batches,
            limit_test_batches=limit_test_batches
        )

    ic("Started trainer")
    trainer = pl.Trainer(**trainer_hparams)

    if old_checkpoint != "":
        model = model.load_from_checkpoint(old_checkpoint, fsa_dict=fsa_dict, reward_val=reward)

    trainer.fit(model, dm)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Input parameters for extractive stage')
    parser.add_argument('--n_gpus', default=1, type=int, help='number of gpus to use')
    parser.add_argument('--train_path', help='path to input json file for a given domain in given language')
    parser.add_argument('--val_path', help='path to intermediate output json file for a given domain in given language')
    parser.add_argument('--test_path', help='path to output json file for a given domain in given language')
    parser.add_argument('--config', default=None, help='which config file to use')
    parser.add_argument('--tokenizer', default='facebook/mbart-large-50', help='which tokenizer to use')
    parser.add_argument('--model', default='facebook/mbart-large-50', help='which model to use')
    parser.add_argument('--is_mt5', type=int, help='is the model mt5')
    parser.add_argument('--exp_name', default='mbart-basline', help='experiment name')
    parser.add_argument('--save_dir', default='checkpoints/', help='where to save the logs and checkpoints')
    parser.add_argument('--target_lang', default='hi', help='what is the target language')
    parser.add_argument('--num_epochs', default=5, type=int, help='number of epochs')
    parser.add_argument('--train_batch_size', default=4, type=int, help='train batch size')
    parser.add_argument('--val_batch_size', default=4, type=int, help='val batch size')
    parser.add_argument('--test_batch_size', default=4, type=int, help='test batch size')
    parser.add_argument('--max_source_length', default=1024, type=int, help='max source length')
    parser.add_argument('--max_target_length', default=1024, type=int, help='max target length')
    parser.add_argument('--strategy', default='dp', help='which strategy to use')
    parser.add_argument('--sanity_run', default='no', help='which strategy to use')
    parser.add_argument('--prediction_path', default='preds.txt', help='path to save prediction file')
    parser.add_argument('--reward', default=0, type=float, help='whether to use fsa reward or not')
    parser.add_argument('--fsa_path', help='path to fsa probs')
    parser.add_argument('--isTrial', default=1, help='is trial')
    parser.add_argument('--beam_size', default=1)
    parser.add_argument('--wandb', default=1, type=int, help='to enable wandb loggings')
    parser.add_argument('--old_checkpoint', default="", type=str, help='mid-checkpoint training')
    parser.add_argument('--learning_rate', default=2e-5, type=float, help='learning rate used')

    args = parser.parse_args()

    main(args)
