# -*- coding: utf-8 -*-
"""Table_Prediction.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Pt812EnYdAHvusyHOdogZkYvNC774ypl
"""

from __future__ import unicode_literals, print_function, division
from io import open
import unicodedata
import string
import re
import random
import spacy

import torch
import torch.nn as nn
from torch import optim
import torch.nn.functional as F

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
ENCODER_PATH = r'/content/table_pred.pth'
print(device)

SOS_token = 0
EOS_token = 1

class Lang:
    def __init__(self, name):
        self.name = name
        self.word2index = {"<UNK>" : 1}
        self.word2count = {"<UNK>" : 1}
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

def readLangs(file):
    print("Reading lines...")
    # Read the file and split into lines
    lines = open('/content/Sent2LogicalForm/data/%s.txt' % (file), encoding='utf-8').read().strip().split('\n')
    # Split every line into pairs and normalize
    pairs = [[normalizeString(s) for s in l.split('   ')] for l in lines]
    # Reverse pairs, make Lang instances
    input_lang = Lang('english')
    output_lang = Lang('sql')
    return input_lang, output_lang, pairs

def prepareData(file):
    input_lang, output_lang, pairs = readLangs(file)
    print("Read %s sentence pairs" % len(pairs))
    print("Trimmed to %s sentence pairs" % len(pairs))
    print("Counting words...")
    for pair in pairs:
        input_lang.addSentence(pair[0])
        output_lang.addWord(pair[1])
    print("Counted words:")
    print(input_lang.name, input_lang.n_words)
    print(output_lang.name, output_lang.n_words)
    return input_lang, output_lang, pairs


input_lang, output_lang, pairs = prepareData('train_tables')
print(random.choice(pairs))

class EncoderRNN(nn.Module):
    def __init__(self, input_size, hidden_size,num_classes):
        super(EncoderRNN, self).__init__()
        self.hidden_size = hidden_size
        self.embedding = nn.Embedding(input_size, hidden_size)
        self.lstm = nn.LSTM(hidden_size, hidden_size,num_layers=1)
        self.linear = nn.Linear(hidden_size,num_classes)
        self.dropout = nn.Dropout(0.2)

    def forward(self, input):
        embedded = self.embedding(input)
        output = embedded
        output, (hidden,context) = self.lstm(output)
        return self.linear(hidden[-1])

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
    return torch.tensor(indexes, dtype=torch.long, device=device).view(-1, 1)

def tensorFromWord(lang,word):
  if word not in lang.word2index:
    index = lang.word2index["UNK"]
  else:
    index = lang.word2index[word]
  return torch.tensor(F.one_hot(torch.tensor([index]), num_classes=lang.n_words),dtype=torch.float32)

def tensorsFromPair(pair):
    input_tensor = tensorFromSentence(input_lang, pair[0])
    target_tensor = tensorFromWord(output_lang,pair[1])
    return (input_tensor, target_tensor)

def train(input_tensor, target_tensor, encoder, encoder_optimizer, max_length=50):
    encoder_optimizer.zero_grad()
    input_length = input_tensor.size(0)
    target_length = target_tensor.size(0)
    loss = 0
    y_pred =  encoder(input_tensor)
    cross_entropy_loss = nn.CrossEntropyLoss()
    loss = cross_entropy_loss(y_pred, target_tensor)
    loss.backward()
    encoder_optimizer.step()
    return loss.item() * target_tensor.shape[0]

import time
import math

def asMinutes(s):
    m = math.floor(s / 60)
    s -= m * 60
    return '%dm %ds' % (m, s)

def timeSince(since, percent):
    now = time.time()
    s = now - since
    es = s / (percent)
    rs = es - s
    return '%s (- %s)' % (asMinutes(s), asMinutes(rs))

def lr_decay(learning_rate_decay,optimizer):
  for param_group in optimizer.param_groups:
    param_group['lr'] = param_group['lr']*learning_rate_decay
  return optimizer

def trainIters(encoder, n_iters=75000, print_every=1000, plot_every=100, learning_rate=0.01):
    start = time.time()
    print_loss_total = 0  # Reset every print_every
    learning_rate_decay =  0.985
    learning_rate_decay_after = 100
    encoder_optimizer = optim.SGD(encoder.parameters(), lr=learning_rate)
    training_pairs = [tensorsFromPair(random.choice(pairs)) for i in range(0,n_iters)]

    for iter in range(1, n_iters + 1):
        training_pair = training_pairs[iter - 1]
        input_tensor = training_pair[0]
        target_tensor = training_pair[1]

        loss = train(input_tensor, target_tensor, encoder,encoder_optimizer)
        print_loss_total += loss

        if iter % print_every == 0:
            print_loss_avg = print_loss_total / print_every
            print_loss_total = 0
            print('%s (%d %d%%) %.4f' % (timeSince(start, iter / n_iters),
                                         iter, iter / n_iters * 100, print_loss_avg))

import spacy
tok = spacy.load('en')
def tokenize (text):
    regex = re.compile('[' + re.escape(string.punctuation) + '0-9\\r\\t\\n]') # remove punctuation and numbers
    nopunct = regex.sub("", text.lower())
    nopunct = re.sub(' +', ' ', nopunct)
    return [token.text for token in tok.tokenizer(nopunct)]
    
def preprocess(sentence):
  return ' '.join(tokenize(sentence))

import matplotlib.pyplot as plt
plt.switch_backend('agg')
import matplotlib.ticker as ticker
import numpy as np

def showPlot(points):
    plt.figure()
    fig, ax = plt.subplots()
    # this locator puts ticks at regular intervals
    loc = ticker.MultipleLocator(base=0.2)
    ax.yaxis.set_major_locator(loc)
    plt.plot(points)

def evaluate(encoder, sentence, max_length=5000):
    sentence = preprocess(sentence)
    with torch.no_grad():
        input_tensor = tensorFromSentence(input_lang, sentence)
        input_length = input_tensor.size()[0]
        y_pred =  encoder(input_tensor)
        return y_pred

def evaluateRandomly(encoder, n=10):
    for i in range(n):
        pair = random.choice(pairs)
        print('>', pair[0])
        print('=', pair[1])
        output_words = evaluate(encoder, pair[0])
        output_sentence = output_words
        print('<', output_sentence)
        print('')

hidden_size = 256
encoder = EncoderRNN(input_lang.n_words, hidden_size,output_lang.n_words).to(device)
trainIters(encoder, 75000, print_every=5000)
evaluateRandomly(encoder)

torch.save(encoder.state_dict(), ENCODER_PATH)

hidden_size = 256
encoder = EncoderRNN(input_lang.n_words, hidden_size,output_lang.n_words).to(device)
encoder.load_state_dict(torch.load(ENCODER_PATH,map_location=torch.device(device)))
output = evaluate(encoder, "what are the maximum and minimum budget of the departments")
print(output_lang.index2word[int(torch.argmax(output))])
