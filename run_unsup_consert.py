import logging
import math
from datetime import datetime
#from transformers import AutoTokenizer, AutoModelForMaskedLM
import torch
from sentence_transformers import InputExample, SentenceTransformer, LoggingHandler
from sentence_transformers import models, losses
from sentence_transformers.ConSERT import ConSERT
from sentence_transformers.evaluation import EmbeddingSimilarityEvaluator, SimilarityFunction
from torch.utils.data import DataLoader

from data.dataset import load_STS_data

#### Just some code to print debug information to stdout
logging.basicConfig(format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO,
                    handlers=[LoggingHandler()])

# 训练参数
model_name = 'A:/chinese-roberta-wwm-ext'
#model_name = None
train_batch_size = 32
num_epochs = 2
max_seq_length = 64
device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
device = "cuda:0"


#tokenizer = AutoTokenizer.from_pretrained("hfl/chinese-roberta-wwm-ext")

#model_name = AutoModelForMaskedLM.from_pretrained("hfl/chinese-roberta-wwm-ext")
# 模型保存路径
model_save_path = 'A:/NLP-Series-sentence-embeddings/output/stsb_consert-{}-{}-{}'.format("macbert",
                                                                                                     train_batch_size,
                                                                                                     datetime.now().strftime(
                                                                                                         "%Y-%m-%d_%H-%M-%S"))

# 建立模型
model = ConSERT(model_name, device=device, cutoff_rate=0.15, close_dropout=True)
#print(type(model))
model.__setattr__("max_seq_length", max_seq_length)

# 准备训练集
sts_vocab = load_STS_data("A:/STS-B/cnsd-sts-train.txt")
all_vocab = [x[0] for x in sts_vocab] + [x[1] for x in sts_vocab]
simCSE_data = all_vocab
print("The len of SimCSE unsupervised data is {}".format(len(simCSE_data)))
train_samples = []
for data in all_vocab:
    train_samples.append(InputExample(texts=[data, data]))

# 准备验证集和测试集
dev_data = load_STS_data("A:/STS-B/cnsd-sts-dev.txt")
test_data = load_STS_data("A:/STS-B/cnsd-sts-test.txt")
dev_samples = []
test_samples = []
for data in dev_data:
    dev_samples.append(InputExample(texts=[data[0], data[1]], label=data[2] / 5.0))
for data in test_data:
    test_samples.append(InputExample(texts=[data[0], data[1]], label=data[2] / 5.0))

# 初始化评估器
dev_evaluator = EmbeddingSimilarityEvaluator.from_input_examples(dev_samples, batch_size=train_batch_size,
                                                                 name='sts-dev',
                                                                 main_similarity=SimilarityFunction.COSINE)
test_evaluator = EmbeddingSimilarityEvaluator.from_input_examples(test_samples, batch_size=train_batch_size,
                                                                  name='sts-test',
                                                                  main_similarity=SimilarityFunction.COSINE)

# We train our model using the MultipleNegativesRankingLoss
train_dataloader = DataLoader(train_samples, shuffle=True, batch_size=train_batch_size)
train_loss = losses.MultipleNegativesRankingLoss(model)

warmup_steps = math.ceil(len(train_dataloader) * num_epochs * 0.1)  # 10% of train data for warm-up
evaluation_steps = int(len(train_dataloader) * 0.1)  # Evaluate every 10% of the data
logging.info("Training sentences: {}".format(len(train_samples)))
logging.info("Warmup-steps: {}".format(warmup_steps))
logging.info("Performance before training")
dev_evaluator(model)

# 模型训练
model.fit(train_objectives=[(train_dataloader, train_loss)],
          evaluator=dev_evaluator,
          epochs=num_epochs,
          evaluation_steps=evaluation_steps,
          warmup_steps=warmup_steps,
          show_progress_bar=False,
          output_path=model_save_path,
          optimizer_params={'lr': 2e-5},
          use_amp=False  # Set to True, if your GPU supports FP16 cores
          )

# 测试集上的表现
model = SentenceTransformer(model_save_path)
test_evaluator(model, output_path=model_save_path)
