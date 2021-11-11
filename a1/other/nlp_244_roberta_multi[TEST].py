# -*- coding: utf-8 -*-
"""NLP-244 Week 3 Section.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1yXNPfO8Mh0H3nAHpumGCkv3GzU2QOr8r

#  NLP 244 Section Week 3: BERT for slot tagging and intent detection

This week we will be using a BERT model  provided by [Dilek and her team](https://github.com/alexa/dialoglue) that was designed for the ATIS dataset. Using this example you should get an idea of how to apply this to the homework.
"""

import torch
from torch import nn
from torch.nn import CrossEntropyLoss
from torch.nn import BCEWithLogitsLoss
from torch.nn import Dropout
from transformers import BertModel, BertTokenizer, BertTokenizerFast
from transformers import RobertaModel, RobertaTokenizerFast
from torch.utils.data import DataLoader
from transformers import AdamW

import os
from tqdm.auto import tqdm
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
print('Running on:', device)


class ParserModel(torch.nn.Module):
    def __init__(self,
                 model_name_or_path: str,
                 dropout: float,
                 num_intent_labels: int,
                 num_slot_labels: int):
        super(ParserModel, self).__init__()
        self.roberta_model = RobertaModel.from_pretrained(model_name_or_path)
        self.dropout = Dropout(dropout)
        self.num_intent_labels = num_intent_labels
        self.num_slot_labels = num_slot_labels
        self.intent_classifier = nn.Linear(self.roberta_model.config.hidden_size, num_intent_labels)
        self.slot_classifier = nn.Linear(self.roberta_model.config.hidden_size, num_slot_labels)

    def forward(self,
                input_ids: torch.tensor,
                attention_mask: torch.tensor,
                intent_label: torch.tensor = None,
                slot_labels: torch.tensor = None
                ):

        last_hidden_states, pooler_output = self.bert_model(input_ids=input_ids,
                                                            attention_mask=attention_mask,
                                                            return_dict=False)

        # print(self.bert_model.config)
        # intent_logits = self.intent_classifier(pooler_output)
        # slot_logits = self.slot_classifier(last_hidden_states)
        intent_logits = self.intent_classifier(self.dropout(pooler_output))
        slot_logits = self.slot_classifier(self.dropout(last_hidden_states))

        loss_fct = CrossEntropyLoss()
        loss_fct_intent = BCEWithLogitsLoss()
        # Compute losses if labels provided
        if intent_label is not None:
            intent_loss = loss_fct_intent(intent_logits.view(-1, self.num_intent_labels), intent_label.float().view(-1, self.num_intent_labels))
        else:
            intent_loss = torch.tensor(0)

        if slot_labels is not None:
            # Only keep active parts of the loss
            if attention_mask is not None:
                active_loss = attention_mask.view(-1) == 1
                active_logits = slot_logits.view(-1, self.num_slot_labels)[active_loss]
                active_labels = slot_labels.view(-1)[active_loss]
                slot_loss = loss_fct(active_logits, active_labels.type(torch.long))
            else:
                slot_loss = loss_fct(slot_logits.view(-1, self.num_slot_labels), slot_labels.view(-1).type(torch.long))
        else:
            slot_loss = torch.tensor(0).cuda() if torch.cuda.is_available() else torch.tensor(0)

        return intent_logits, slot_logits, slot_loss, intent_loss


file_train = os.path.join('data', 'train.csv')
df_train = pd.read_csv(file_train, engine='python')
df_train = df_train.fillna('no_intent')

train_split, dev_split = train_test_split(df_train, test_size=0.25, random_state=42)

df_train = train_split
df_dev = dev_split
df_dev[['IOB Slot tags', 'Core Relations']].to_csv('hw1_labels_dev.txt', sep='\t', header=None, index=None)

train_sentences = []
train_slots = []
train_intents = []
train_len = []
slot_vocab = ['O', 'PAD']
intent_vocab = ['O', 'PAD']
for utt in df_train['utterances']:
    sent = []
    for word in utt.split():
        sent.append(word)
    train_sentences.append(sent)
    train_len.append(len(sent))

for slot in df_train['IOB Slot tags']:
    sent = []
    for tag in slot.split():
        sent.append(tag)
        if tag not in slot_vocab:
            slot_vocab.append(tag)
    train_slots.append(sent)

for rel in df_train['Core Relations']:
    sent = []
    rel = str(rel)

    for word in rel.split():
        sent.append(word)
        if word not in intent_vocab:
            intent_vocab.append(word)
    train_intents.append(sent)


dev_sentences = []
dev_len = []
for utt in df_dev['utterances']:
    sent = []
    for word in utt.split():
        sent.append(word)
    dev_sentences.append(sent)
    dev_len.append(len(sent))


file_test = os.path.join('data', 'test.csv')
df_test = pd.read_csv(file_test, engine='python')
test_sentences = []
test_len = []
for utt in df_test['utterances']:
    sent = []
    for word in utt.split():
        sent.append(word)
    test_len.append(len(sent))
    test_sentences.append(sent)


#print('slot vocab:', slot_vocab)
#print('intent vocab:', intent_vocab)
train_sentences = train_sentences[:10]
train_slots = train_slots[:10]
train_intents = train_intents[:10]
train_len = train_len[:10]

"""# Typical Huggingface Workflow:

1. Make forward mappings and inverse mappings based on unique input vocab and unique output vocab(s). Forward helps for training, inverse helps with inference.
2. Load your model tokenizer and specifiy appropriate parameters: padding, truncation... etc.
3. Do a train-test split (This example has only 2 examples lol)
4. Encode the input texts in your splits.
5. Encode the labels for your texts.
6. Create a PyTorch class so you can utilize batching easily during training. An example of this is given below.
7. Load your pretrained HuggingFace model.
8. Write your training/validation loop
9. Run evaluation
10. Run Inference if evaluation is satisfactory.

```
class OurDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)
```
"""

# 1. For mapping slots and intents between ints and string
slot2id = {slot: id for id, slot in enumerate(slot_vocab)}
id2slot = {id: slot for slot, id in slot2id.items()}

intent2id = {intent: id for id, intent in enumerate(intent_vocab)}
id2intent = {id: intent for intent, id in intent2id.items()}

# 2. Tokenize utterances for BERT to accept
# Load pre-trained model tokenzier (vocab)
tokenizer = RobertaTokenizerFast.from_pretrained('roberta-base', add_prefix_space=True)

# 3. Train-test split if have enough data

# 4. pads to longest sequence, truncates to maximum allowed length by model, 
# Gives encodings, token type_ids -> https://huggingface.co/transformers/glossary.html#token-type-ids and attention_masks
# and offset_mappings
train_encodings = tokenizer(train_sentences, return_offsets_mapping=True, is_split_into_words=True, padding=True,
                            truncation=True)
dev_encodings = tokenizer(dev_sentences, return_offsets_mapping=False, is_split_into_words=True, padding=True,
                            truncation=True)
test_encodings = tokenizer(test_sentences, return_offsets_mapping=False, is_split_into_words=True, padding=True,
                           truncation=True)

# 5. Encoding labels

def encode_labels(tags, encodings, mapping):
    labels = [[mapping[tag] for tag in doc] for doc in tags]
    encoded_labels = []
    for doc_labels, doc_offset in zip(labels, encodings.offset_mapping):
        # create an empty array of -100
        doc_enc_labels = np.ones(len(doc_offset), dtype=int) * -100
        arr_offset = np.array(doc_offset)
        # set labels whose first offset position is 0 and the second is not 0
        doc_enc_labels[(arr_offset[:, 0] == 0) & (arr_offset[:, 1] != 0)] = doc_labels
        encoded_labels.append(doc_enc_labels.tolist())

    return encoded_labels


def encode_intents(intents, mapping, intent_vocab_len):

    #labels = [mapping[intent] for intent in intents]
    labels = [[mapping[intent] for intent in doc] for doc in intents]
    one_hot = []
    for line in labels:
        temp = [0] * intent_vocab_len
        for x in line:
            temp[x] = 1
        one_hot.append(temp)

    return one_hot

print(train_encodings)
train_slot_labels = encode_labels(train_slots, train_encodings, slot2id)
train_intent_labels = encode_intents(train_intents, intent2id, len(intent_vocab))



# 6. Make your dataset
class ATISDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, slot_labels, intent_labels):
        self.encodings = encodings
        self.slot_labels = slot_labels
        self.intent_labels = intent_labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['slot_labels'] = torch.tensor(self.slot_labels[idx])
        item['intent_labels'] = torch.tensor(self.intent_labels[idx])
        return item

    def __len__(self):
        return len(self.slot_labels)


class OurDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, sentence_len):
        self.encodings = encodings
        self.sentence_len = sentence_len

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        return item

    def __len__(self):
        return len(self.sentence_len)


train_encodings.pop("offset_mapping")  # we don't want to pass this to the model
train_dataset = ATISDataset(train_encodings, train_slot_labels, train_intent_labels)

dev_dataset = OurDataset(dev_encodings, dev_len)
test_dataset = OurDataset(test_encodings, test_len)

# 7. Define huggingface model
dropout = 0.2
num_intent_labels = len(intent_vocab)
num_slot_labels = len(slot_vocab)

model = ParserModel(model_name_or_path='roberta-base',
                    dropout=dropout,
                    num_intent_labels=num_intent_labels,
                    num_slot_labels=num_slot_labels,
                    )

def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


count_parameters(model)
# 109,603,742, 109M trainable params compared to 65M with DistilBERT in previous section example.

# 8. Training

model.to(device)
model.train()

train_loader = DataLoader(train_dataset, batch_size=1, shuffle=True)
# 'W' stands for 'Weight Decay fix"
# Note: AdamW is a class from the huggingface library (as opposed to pytorch) 
optim = AdamW(model.parameters(), lr=5e-5)

# Number of training epochs (authors recommend between 2 and 4)
# input_ids: torch.tensor,
#                 attention_mask: torch.tensor,
#                 token_type_ids: torch.tensor,
#                 intent_label: torch.tensor = None,
#                 slot_labels: torch.tensor = None
for epoch in tqdm(range(3)):
    for batch in train_loader:
        optim.zero_grad()
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        slot_labels = batch['slot_labels'].to(device)
        intent_labels = batch['intent_labels'].to(device)
        outputs = model(input_ids=input_ids,
                        attention_mask=attention_mask,
                        slot_labels=slot_labels,
                        intent_label=intent_labels)
        slot_loss, intent_loss = outputs[2], outputs[3]
        slot_loss.backward(retain_graph=True)  # need to retain_graph  when working with multiple losses
        intent_loss.backward()
        optim.step()

model.eval()

# 9. DO Evaluation if have validation set or you can do this during training.
model.eval()
model.to(device)
val_loader = DataLoader(dev_dataset, batch_size=1, shuffle=False)  # reusing training set lol
losses = []
idx_dev = 0
all_slot_eval = []
all_intent_eval = []
for batch in val_loader:
    input_ids = batch['input_ids'].to(device)
    attention_mask = batch['attention_mask'].to(device)

    outputs = model(input_ids=input_ids,
                    attention_mask=attention_mask,
                    slot_labels=None,
                    intent_label=None)
    intent_logits, slot_logits = outputs[0], outputs[1]
    slot_loss, intent_loss = outputs[2], outputs[3]

    # slots
    probability_value = torch.softmax(slot_logits, dim=2)
    idxs = torch.argmax(probability_value, dim=2)
    # intent

    intent_probability_value = torch.softmax(intent_logits, dim=1)
    intent_idxs = torch.argmax(intent_probability_value, dim=1)

    test_multi = torch.sigmoid(intent_logits)
    converted = []
    for id in test_multi[0]:
        if id >= 0.4:
            converted.append(1)
        else:
            converted.append(0)
    test_idx = [i for i, x in enumerate(converted) if x == 1]

    # true = [id2tag[id.item()] for id in labels[0]]
    slot_prediction = [id2slot[id.item()] for id in idxs[0]]
    intent_prediction = [id2intent[id.item()] for id in intent_idxs]
    test_intent_prediction = [id2intent[id] for id in test_idx]
    if len(test_intent_prediction) == 0:
        test_intent_prediction.append('no_intent')

    #print(test_intent_prediction)
    #print(slot_prediction[1:train_len[idx_train]+1], intent_prediction)
    all_slot_eval.append(slot_prediction[1:dev_len[idx_dev] + 1])
    all_intent_eval.append(test_intent_prediction)
    idx_dev += 1
    #print(slot_loss, intent_loss)

# write to file
file_dev = open('prediction_dev.txt', 'w')
for i in range(len(all_intent_eval)):
    line = ' '
    line2 = ' '
    out = line.join(all_slot_eval[i]) + '\t' + line2.join(all_intent_eval[i])
    file_dev.write(out + '\n')
file_dev.close()

# 10. Inference, you have to do inference to generate your prediction.txt for hw1
model.eval()
model.to(device)
test_loader = DataLoader(test_dataset, batch_size=1, shuffle=False)  # reusing training set lol
losses = []
idx_len = 0
all_slot_pred = []
all_intent_pred = []
for batch in test_loader:
    input_ids = batch['input_ids'].to(device)
    attention_mask = batch['attention_mask'].to(device)
    # slot_labels = batch['slot_labels'].to(device)
    # intent_labels = batch['intent_labels'].to(device)
    outputs = model(input_ids=input_ids,
                    attention_mask=attention_mask,
                    slot_labels=None,
                    intent_label=None)
    intent_logits, slot_logits = outputs[0], outputs[1]
    # slot_loss, intent_loss = outputs[2], outputs[3]

    # slots
    probability_value = torch.softmax(slot_logits, dim=2)
    idxs = torch.argmax(probability_value, dim=2)
    # intent
    intent_probability_value = torch.softmax(intent_logits, dim=1)
    intent_idxs = torch.argmax(intent_probability_value, dim=1)
    # true = [id2tag[id.item()] for id in labels[0]]
    slot_prediction = [id2slot[id.item()] for id in idxs[0]]
    intent_prediction = [id2intent[id.item()] for id in intent_idxs]
    #print(slot_prediction[1:test_len[idx_len]+1], intent_prediction)
    all_slot_pred.append(slot_prediction[1:test_len[idx_len]+1])
    all_intent_pred.append(intent_prediction)
    idx_len += 1
    # print(slot_loss, intent_loss)
    # In your submissions you need to clean output to dimensions of test set remove uneccessary padding.


# write to file
file_pred = open('submission.txt', 'w')
for i in range(len(all_intent_pred)):
    line = ' '
    line2 = ' '
    out = line.join(all_slot_pred[i]) + '\t' + line2.join(all_intent_pred[i])
    file_pred.write(out + '\n')
file_pred.close()