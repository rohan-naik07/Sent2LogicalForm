import unicodedata
import json
import spacy
import torch

nlp = spacy.load("en_core_web_sm")
print("loaded")

SQL_FUNC_VOCAB = ['avg','count','first','last','sum','min','max','date','year','for','by']

sql_literals = {
    'column' : '<attr>',
    'alais' : '<al>',
    'table' : '<table>'
}


STD_SQL_QUERY_TOKEN = {
    "select",
    "distinct",
    "agg"
    "column"
    "from",
    "table",
    "where",
    "column",
    "op",
    "value",
    "groupBy",
    "having",
    "orderBy",
    "limit",
    "intersect",
    "union",
    "except"
}

SOS_token = 0
EOS_token = 1

class Lang:
    def __init__(self, name):
        self.name = name
        self.word2index = {}
        self.word2count = {}
        self.index2word = {0: "SOS", 1: "EOS",2:"<UNK>"}
        self.n_words = 3  # Count SOS and EOS

    def addSentence(self, sentence):
        for word in sentence.split(' '):
            self.addWord(word)

    def addWord(self, word):
        if word not in self.word2index:
            self.word2index[word] = self.n_words
            self.word2count[word] = 1
            self.index2word[self.n_words] = word
            self.n_words += 1
        else:
            self.word2count[word] += 1

def unicodeToAscii(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

# Lowercase, trim, and remove non-letter characters
def normalizeString(s):
    s = unicodeToAscii(s.lower().strip())
    return s



def getLangs():
    input_lang = Lang('english')
    output_lang = Lang('sql')
     # Read the file and split into lines
    lines = open(r'C:\Users\admin\Desktop\Sent2LogicalForm\data\train_spider.txt', encoding='utf-8').read().strip().split('\n')
    # Split every line into pairs and normalize
    pairs = [[normalizeString(s) for s in l.split('   ')] for l in lines]
    for pair in pairs:
        input_lang.addSentence(pair[0])
        output_lang.addSentence(pair[1])
    return input_lang, output_lang
    
def indexesFromSentence(lang, sentence):
    result=[]
    for word in sentence.split(' '):
      if word not in lang.word2index:
        result.append(1)
      else : result.append(lang.word2index[word])
    return result

def tensorFromSentence(lang, sentence):
    indexes = indexesFromSentence(lang, sentence)
    indexes.append(EOS_token)
    return torch.tensor(indexes, dtype=torch.long, device="cpu").view(-1, 1)

def get_sql_vocab():
    sql_vocab={}
    with open(r'C:\Users\admin\Desktop\Sent2LogicalForm\data\sql_vocab.txt') as vocab_file:
        tokens = vocab_file.readlines()
        for token in tokens:
            sql_vocab[token.lower()] = True
    return sql_vocab

def get_tables_info():
    table_props={}
    with open(r'C:\Users\admin\Desktop\Sent2LogicalForm\data\tables.json') as file:
        table_data = json.load(file)
        for entry in table_data:
            table_props[entry['db_id']] = {}
            table_props[entry['db_id']]['columns'] = [column[1].lower() for column in entry['column_names_original']]
            if 'table_names' in table_props:
                for table_name in entry['table_names_original']:
                    table_props['table_names'][table_name] = True
            else: table_props['table_names'] = {}
    return table_props


def preprocess(sentence):
  tokens = sentence.lower().split()
  for i in range(0,len(tokens)):
      pos_tag = nlp(tokens[i])[0]
      if pos_tag.pos_ not in ['PUNCT']:
        tokens[i] = pos_tag.lemma_
      elif tokens[i].isdigit()==True:
        tokens[i] = "value"
  return ' '.join(tokens)