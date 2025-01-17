from torch.utils.data import Dataset, DataLoader
import pytorch_lightning as pl
from transformers import AutoTokenizer
import pandas as pd
import json
import pytorch_lightning as pl
from pytorch_lightning.loggers import WandbLogger
from indicnlp.transliterate import unicode_transliterate
from transformers import MBartForConditionalGeneration, MT5ForConditionalGeneration, AutoConfig, AutoModelForSeq2SeqLM, MBartTokenizer
import torch
import argparse
from rouge import Rouge
import sys
sys.setrecursionlimit(1024 * 1024 + 10)

class Dataset1(Dataset):
    def __init__(self, data_path, tokenizer, max_source_length, max_target_length, is_mt5):
        fp = open(data_path, 'r')
        self.df = [json.loads(line, strict=False) for line in fp.readlines()]
        self.tokenizer = tokenizer
        self.max_source_length = max_source_length
        self.max_target_length = max_target_length
        self.is_mt5 = is_mt5
        self.languages_map = {
            'bn': {0:'bn_IN'},
            'de': {0:'de_DE'},
            'en': {0:'en_XX'},
            'es': {0:'es_XX'},
            'fr': {0:'fr_XX'},
            'gu': {0:'gu_IN'},
            'hi': {0:'hi_IN'},
            'it': {0:'it_IT'},
            'kn': {0:'kn_IN'},
            'ml': {0:'ml_IN'},
            'mr': {0:'mr_IN'},
            'or': {0:'or_IN'},
            'pa': {0:'pa_IN'},
            'ta': {0:'ta_IN'},
            'te': {0:'te_IN'}
        }
        self.intro_map = {
            'bn': 'ভূমিকা',
            'en': 'Introduction',
            'hi': 'परिचय',
            'kn': 'ಪರಿಚಯ',
            'ml': 'ആമുഖം',
            'mr': 'परिचय',
            'or': 'ପରିଚୟ',
            'pa': 'ਜਾਣ-ਪਛਾਣ',
            'ta': 'அறிமுகம்',
            'te': 'పరిచయం'
        }



    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        article = self.df[idx]['article']
        article_title = article['title']
        sections = ""

        # if self.is_mt5:
        #     self.septoken = '<SEP>'
        # else:
        #     self.septoken = '</s>'

        lang = self.df[idx]['language']
        if lang not in self.languages_map:
            lang='en'
        xlang = lang
        lang = self.languages_map[lang][0]

        for section in article['sections']:
            if section['title'] == 'Introduction':
                sections = f'{sections} {self.intro_map[xlang]} '
            else:
                sections = f'{sections} {section["title"]} '

        domain = self.df[idx]['domain']
        input_text = f'{lang} {domain} {article_title}'

        target_text = sections

        # if self.is_mt5:
        #     self.tokenizer.add_special_tokens({'sep_token': '</s>'})


        input_encoding = self.tokenizer(input_text, return_tensors='pt', max_length=self.max_source_length ,padding='max_length', truncation=True)
        target_encoding = self.tokenizer(lang + target_text, return_tensors='pt', max_length=self.max_target_length ,padding='max_length', truncation=True)

        input_ids, attention_mask = input_encoding['input_ids'], input_encoding['attention_mask']
        labels = target_encoding['input_ids']

        if self.is_mt5:
            labels[labels == self.tokenizer.pad_token_id] = -100    # for ignoring the cross-entropy loss at padding locations


        return {'input_ids': input_ids.squeeze(), 'attention_mask': attention_mask.squeeze(), 'labels': labels.squeeze(), 'lang': lang, 'domain': domain}


class DataModule(pl.LightningDataModule):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.save_hyperparameters()
        self.tokenizer = AutoTokenizer.from_pretrained(self.hparams.tokenizer_name_or_path)

    def setup(self, stage=None):
        self.train = Dataset1(self.hparams.train_path, self.tokenizer, self.hparams.max_source_length, self.hparams.max_target_length, self.hparams.is_mt5)
        self.val = Dataset1(self.hparams.val_path, self.tokenizer, self.hparams.max_source_length, self.hparams.max_target_length, self.hparams.is_mt5)
        self.test = Dataset1(self.hparams.test_path, self.tokenizer, self.hparams.max_source_length, self.hparams.max_target_length, self.hparams.is_mt5)

    def train_dataloader(self):
        return DataLoader(self.train, batch_size=self.hparams.train_batch_size, num_workers=1,shuffle=True)

    def val_dataloader(self):
        return DataLoader(self.val, batch_size=self.hparams.val_batch_size, num_workers=1,shuffle=False)

    def test_dataloader(self):
        return DataLoader(self.test, batch_size=self.hparams.test_batch_size, num_workers=1,shuffle=False)

    def predict_dataloader(self):
        return self.test_dataloader()


class Summarizer(pl.LightningModule):
    def __init__(self, *args, **kwargs):
        super().__init__()
        # print(self.hparams)
        self.save_hyperparameters()
        self.rouge = Rouge()
        # self.config = AutoConfig.from_pretrained(self.hparams.config)
        # print(self.hparams)
        if self.hparams.is_mt5:
            self.model = MT5ForConditionalGeneration.from_pretrained(self.hparams.model_name_or_path)
        else:
            self.model = MBartForConditionalGeneration.from_pretrained(self.hparams.model_name_or_path)

        self.languages_map = {
            'bn': {0:'bn_IN'},
            'de': {0:'de_DE'},
            'en': {0:'en_XX'},
            'es': {0:'es_XX'},
            'fr': {0:'fr_XX'},
            'gu': {0:'gu_IN'},
            'hi': {0:'hi_IN'},
            'it': {0:'it_IT'},
            'kn': {0:'kn_IN'},
            'ml': {0:'ml_IN'},
            'mr': {0:'mr_IN'},
            'or': {0:'or_IN'},
            'pa': {0:'pa_IN'},
            'ta': {0:'ta_IN'},
            'te': {0:'te_IN'}
        }


        # self.languages_map = {
        #     'bn': 'bn_IN',
        #     'de': 'de_DE',
        #     'en': 'en_XX',
        #     'es': 'es_XX',
        #     'fr': 'fr_XX',
        #     'gu': 'gu_IN',
        #     'hi': 'hi_IN',
        #     'it': 'it_IT',
        #     'kn': 'kn_IN',
        #     'ml': 'ml_IN',
        #     'mr': 'mr_IN',
        #     'or': 'or_IN',
        #     'pa': 'pa_IN',
        #     'ta': 'ta_IN',
        #     'te': 'te_IN',
        # }



    def forward(self, input_ids, attention_mask, labels):
        outputs = self.model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
        return outputs

    def _step(self, batch):
        input_ids, attention_mask, labels, src_lang, tgt_lang = batch['input_ids'], batch['attention_mask'], batch['labels'], batch['lang'], batch['domain']
        outputs = self(input_ids, attention_mask, labels)
        loss = outputs[0]
        return loss

    def _generative_step(self, batch):

        if not self.hparams.is_mt5:
            try:
                token_id = self.hparams.tokenizer.lang_code_to_id[batch['lang'][0]]
                self.hparams.tokenizer.tgt_lang = batch['lang'][0]
            except:
                token_id = 250044
                self.hparams.tokenizer.tgt_lang = 'ta_IN'

            generated_ids = self.model.generate(
                input_ids=batch['input_ids'],
                attention_mask=batch['attention_mask'],
                use_cache=True,
                num_beams=self.hparams.eval_beams,
                forced_bos_token_id=token_id,
                max_length=self.hparams.tgt_max_seq_len #understand above 3 arguments
                )
        else:
            self.hparams.tokenizer.tgt_lang = batch['lang'][0]
            generated_ids = self.model.generate(
                input_ids=batch['input_ids'],
                attention_mask=batch['attention_mask'],
                use_cache=True,
                num_beams=self.hparams.eval_beams,
                max_length=self.hparams.tgt_max_seq_len #understand above 3 arguments
                )


        input_text = self.hparams.tokenizer.batch_decode(batch['input_ids'], skip_special_tokens=True)
        pred_text = self.hparams.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)
        if self.hparams.is_mt5:
            batch['labels'][batch['labels'] == -100] = self.hparams.tokenizer.pad_token_id
        ref_text = self.hparams.tokenizer.batch_decode(batch['labels'], skip_special_tokens=True)

        return input_text, pred_text, ref_text, batch['lang'], batch['domain']


    def training_step(self, batch, batch_idx):
        loss = self._step(batch)
        self.log("train_loss", loss, on_epoch=True)
        return {'loss': loss}

    def validation_step(self, batch, batch_idx):
        loss = self._step(batch)
        # input_text, pred_text, ref_text = self._generative_step(batch)
        self.log("val_loss", loss, on_epoch=True)
        return

    def validation_epoch_end(self, outputs):

        return


    def predict_step(self, batch, batch_idx):
        input_text, pred_text, ref_text, src_lang, tgt_lang = self._generative_step(batch)
        return {'input_text': input_text, 'pred_text': pred_text, 'ref_text': ref_text}

    def get_native_text_from_unified_script(self, unified_text, lang):
        return unicode_transliterate.UnicodeIndicTransliterator.transliterate(unified_text, "hi", lang)

    def process_for_rouge(self, text, lang):
        native_text = text
        if lang!='en':
            # convert unified script to native langauge text
            native_text = self.get_native_text_from_unified_script(text, lang)
        native_text = native_text.strip()
        # as input and predicted text are already space tokenized
        native_text = ' '.join([x for x in native_text.split()])
        return native_text

    def test_step(self, batch, batch_idx):
        loss = self._step(batch)
        input_text, pred_text, ref_text, lang, domain = self._generative_step(batch)
        return {'test_loss': loss, 'input_text': input_text, 'pred_text': pred_text, 'ref_text': ref_text, 'lang': lang, 'domain': domain}

    def test_epoch_end(self, outputs):
        input_texts = []
        pred_texts = []
        ref_texts = []
        langs = []
        domains = []
        for x in outputs:
            if x['pred_text'][0] == '':
                x['pred_text'][0] = 'pred_text'
            if x['ref_text'][0] == '':
                x['ref_text'][0] = 'ref_text'
            input_texts.extend(x['input_text'])
            pred_texts.extend(x['pred_text'])
            ref_texts.extend(x['ref_text'])
            langs.extend(x['lang'])
            domains.extend(x['domain'])


        df_to_write = pd.DataFrame()
        df_to_write['input_texts'] = input_texts
        df_to_write['lang'] = langs
        df_to_write['domain'] = domains
        df_to_write['ref_text'] = ref_texts
        df_to_write['pred_text'] = pred_texts
        df_to_write.to_csv(method + '_' + model_name.replace('google/', '').replace('facebook/', '') + '.csv', index=False)

        t = model_name.replace('google/', '').replace('facebook/', '')
        logger.log_text(f'{method}_{t}_predictions', dataframe=df_to_write)


    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.hparams.learning_rate)

    @staticmethod
    def add_model_specific_args(parent_parser):
        parser = parent_parser.add_argument_group('Bart Fine-tuning Parameters')
        parser.add_argument('--learning_rate', default=2e-5, type=float)
        parser.add_argument('--model_name_or_path', default='bart-base', type=str)
        parser.add_argument('--eval_beams', default=3, type=int)
        parser.add_argument('--tgt_max_seq_len', default=128, type=int)
        parser.add_argument('--tokenizer', default='bart-base', type=str)
        return parent_parser

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Input parameters for extractive stage')
    parser.add_argument('--batch_size', default=1, type=int, help='test_batch_size')
    parser.add_argument('--train_path', default=None, help='path to input json file for a given domain in given language')
    parser.add_argument('--val_path', default=None, help='path to intermediate output json file for a given domain in given language')
    parser.add_argument('--test_path', default=None, help='path to output json file for a given domain in given language')
    parser.add_argument('--config', default=None, help='which config file to use')
    parser.add_argument('--tokenizer', default='facebook/mbart-large-50', help='which tokenizer to use')
    parser.add_argument('--model', default='facebook/mbart-large-50', help='which model to use')
    # parser.add_argument('--target_lang', default='hi_IN', help='what is the target language')
    parser.add_argument('--ckpt_path', help='ckpt path')
    parser.add_argument('--exp_name', help='experimet name')
    parser.add_argument('--is_mt5', type=int, help='is the model mt5')
    parser.add_argument('--prediction_path', default='preds.txt', help='path to save prediction file')

    args = parser.parse_args()
    prediction_path = args.prediction_path

    ckpt_path = args.ckpt_path
    ckpt_path_1 = ckpt_path.split('/')[-1]

    method = args.exp_name
    domain = 'all'
    model_name = args.exp_name

    tokenizer = args.tokenizer
    model_name = args.model
    is_mt5 = args.is_mt5

    print('-----------------------------------------------------------------------------------------------------------')
    print(method, domain, model_name)

    train_path = args.train_path
    test_path = args.test_path
    val_path= args.val_path
    # train_path = ckpt_path_1.split('_')[1] + domain + '/' + domain + '_train.json'
    # val_path = ckpt_path_1.split('_')[1] + domain + '/' + domain + '_val.json'
    # test_path = ckpt_path_1.split('_')[1] + domain + '/' + domain + '_test.json'

    # train_path = f'hiporank_output_data/{domain}/{domain}_train.json'
    # val_path = f'hiporank_output_data/{domain}/{domain}_val.json'
    # test_path = f'hiporank_output_data/{domain}/{domain}_test.json'

    # if 'mt5' in model_name:
    #     # tokenizer = 'google/mt5-base'
    #     # model_name = 'google/mt5-base'
    #     is_mt5 = 1
    # else:
    #     tokenizer = 'facebook/mbart-large-50'
    #     model_name = 'facebook/mbart-large-50'
    #     is_mt5 = 0

    dm_hparams = dict(
            train_path=train_path,
            val_path=val_path,
            test_path=test_path,
            tokenizer_name_or_path=tokenizer,
            is_mt5=is_mt5,
            max_source_length=512,
            max_target_length=512,
            train_batch_size=1,
            val_batch_size=1,
            test_batch_size=args.batch_size
            # target_lang=args.target_lang
            )
    dm = DataModule(**dm_hparams)

    model_hparams = dict(
            learning_rate=2e-5,
            model_name_or_path=model_name,
            eval_beams=4,
            is_mt5=is_mt5,
            tgt_max_seq_len=512,
            tokenizer=dm.tokenizer,
            # target_lang=args.target_lang,
            # prediction_path=args.prediction_path
        )

    model = Summarizer(**model_hparams)
    logger=WandbLogger(name='inference_' + method + '_' + domain +  '_' + model_name, save_dir='./', project='multilingual evaluation', log_model=False)
    trainer = pl.Trainer(gpus=1,logger=logger)

    model = model.load_from_checkpoint(ckpt_path)
    results = trainer.test(model=model, datamodule=dm, verbose=True)
    print('-----------------------------------------------------------------------------------------------------------')
