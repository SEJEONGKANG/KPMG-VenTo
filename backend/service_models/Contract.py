# -*- coding: utf-8 -*-
"""contract together cpu.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/15kuC89ePUgSrHSlyenzrN1iSMBPZgP1K
"""

import re
from PyPDF2 import PdfReader
from transformers import pipeline

from captum.attr import LayerIntegratedGradients
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import numpy as np
#from captum.attr import visualization as viz

class Contract_Model():
    def __init__(self, pdf_file, threshold=0.9, device=-1):
        self.pdf_file = pdf_file
        self.threshold = threshold
        self.device = device
        self.result = {}

    def predict(self):

      def find_element_index(lst, element_prefix):
          for index, element in enumerate(lst):
              if element.startswith(element_prefix):
                  return index
          return -1

      def add_element_prefix(lst):
          prefix_pattern = re.compile(r"\n*제[0-9]+조\(.*?(?=\n)")
          last_prefix = None
          for index, element in enumerate(lst):
              match = re.search(prefix_pattern, element)
              if match:
                  last_prefix = match.group()
              elif last_prefix:
                  lst[index] = last_prefix + element
          return lst

      def clean_pdf_text(x):
          x = x.replace('\n',' ') # \n 제거
          x = x.replace('"',"'") # 중간에 "" 오류 제거
          for i in ['①','②','③','④','⑤','⑥','⑦','⑧','⑨','⑩','⑪','⑫','⑬','⑭','⑮']: # 특수문자 제거
            x = x.replace(i,'')
          x = re.sub(r"- [0-9]+ -", "", x) #페이지 제거
          x = re.sub(r'[\(\)]', '', x) # (,) 제거
          x = re.sub(r'[\[\]]', '', x) # [.] 제거
          x = re.sub(r'\s+', ' ', x) # 공백 두 칸 이상 한 칸으로 치환
          x = x.strip() # 양 끝 공백 제거
          return x

      def clean_pdf_text2(x):
          x = x.replace('\n',' ') # \n 제거
          x = x.replace('"',"'") # 중간에 "" 오류 제거
          x = re.sub(r'\s+', ' ', x) # 공백 두 칸 이상 한 칸으로 치환
          x = x.strip() # 양 끝 공백 제거
          return x

      def create_lst(self):
        lst = self.predict()
        return lst

      reader = PdfReader(self.pdf_file)

      contract_text = ""
      for i in range(len(list(reader.pages))):
          page = reader.pages[i]
          contract_text += page.extract_text() 

      results = contract_text.split('.')
      contracts_raw = []
      for i in range(len(results)):
        if len(results[i]) >= 4:
          contracts_raw.append(results[i])

      result = clean_pdf_text(contract_text)
      results = result.split('.')
      contracts = []
      for i in range(len(results)):
        if len(results[i]) >= 4:
          contracts.append(results[i])

      index_start = find_element_index(contracts, ' 제2조')
      index_end = find_element_index(contracts, ' 상기 계약내용을 확인')

      if index_start == -1:
        index_start = 10

      contracts_raw = contracts_raw[index_start:index_end]
      contracts = contracts[index_start:index_end]
      contracts_raw = add_element_prefix(contracts_raw)

      classifier = pipeline("text-classification", model='jhn9803/Contract-base-tokenizer-mDeBERTa-v3-kor-further',device= self.device)

      model2_result = []
      threshold = self.threshold
      for idx,item in enumerate(contracts):
        preds = classifier(item, return_all_scores=True)

        if 1-preds[0][1]['score'] >= threshold:
          #print(contracts_raw[idx])
          #print("불리 확률 : ", 1 - preds[0][0]['score'])
          text = clean_pdf_text2(contracts_raw[idx])
          if len(text[text.find(")")+1:]) > 10:
            result_text = [text[:text.find(")")+1],text[text.find(")")+1:]]
            model2_result.append(result_text)
            #print(model2_result)
      return model2_result
      
    def create_lst(self):
      lst = self.predict()
      return lst

class Contract_Model_Attention():
    def __init__(self, text):
        self.text = text
        #self.device = device
        
    def get_attention(self):

        model_name = "jhn9803/Contract-new-tokenizer-mDeBERTa-v3-kor-further"
        #model_name = "jhn9803/Contract-base-tokenizer-mDeBERTa-v3-kor-further"

        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        #model.to(self.device)
        model.eval()
        tokenizer = AutoTokenizer.from_pretrained(model_name)

        def model_output(inputs):
          return model(inputs)[0]

        model_input = model.deberta.embeddings.word_embeddings

        lig = LayerIntegratedGradients(model_output, model_input)

        def construct_input_and_baseline(text):

            max_length = 510
            baseline_token_id = tokenizer.pad_token_id 
            sep_token_id = tokenizer.sep_token_id 
            cls_token_id = tokenizer.cls_token_id 

            text_ids = tokenizer.encode(text, max_length=max_length, truncation=True, add_special_tokens=False)
          
            input_ids = [cls_token_id] + text_ids + [sep_token_id]
            token_list = tokenizer.convert_ids_to_tokens(input_ids)
            
            baseline_input_ids = [cls_token_id] + [baseline_token_id] * len(text_ids) + [sep_token_id]
            return torch.tensor([input_ids], device='cpu'), torch.tensor([baseline_input_ids], device='cpu'), token_list

        def summarize_attributions(attributions):

            attributions = attributions.sum(dim=-1).squeeze(0)
            attributions = attributions / torch.norm(attributions)
            
            return attributions

        def interpret_text(text, true_class):

            input_ids, baseline_input_ids, all_tokens = construct_input_and_baseline(text)
            attributions, delta = lig.attribute(inputs= input_ids,
                                            baselines= baseline_input_ids,
                                            return_convergence_delta=True,
                                            internal_batch_size=1,
                                            target = true_class                                    
                                            )
            attributions_sum = summarize_attributions(attributions)

            """
            score_vis = viz.VisualizationDataRecord(
                                word_attributions = attributions_sum,
                                pred_prob = torch.max(model(input_ids)[0]),
                                pred_class = torch.argmax(model(input_ids)[0]).cpu().numpy(),
                                true_class = true_class,
                                attr_class = text,
                                attr_score = attributions_sum.sum(),       
                                raw_input_ids = all_tokens,
                                convergence_score = delta)

            viz.visualize_text([score_vis])
            """

            return all_tokens, attributions_sum

        text = self.text
        true_class = 1
        all_tokens, attributions_sum = interpret_text(text, true_class)

        attention_dict = {}

        for idx, string in enumerate(all_tokens):
            chars = list(string)
            for char in chars:
                attention_dict[char] = abs(round(float(attributions_sum[idx]),4))

        tokenized_sentence = [token for token in text if token not in tokenizer.all_special_tokens]

        original_sentence = tokenizer.convert_tokens_to_string(tokenized_sentence)

        attention = []
        for i in list(original_sentence):
          if i in attention_dict:
            attention.append(attention_dict[i])
          else:
            attention.append(0)
      
        return attention
      
    def create_lst(self):
      lst = self.get_attention()
      return lst
"""
threshold = 0.9
contract = Contract_Model('C:/Users/sjkan/Desktop/KPMG Signals Repository 기업정보 데이터/합작투자계약서_국문.pdf', threshold) #pdf, 기준치
result = contract.create_lst()

result

  #react에서 받아온 str list~
  contract_wanna_check = ["계약조항위반을 한번 용인하였다고 하여 동 조항 위 반의 계속적 묵인이나 동 조항의 변경 · 포기로 간주되지 아니한다", "본 계약의 변경 및 수정은 본 계약일 이후에 서면으로 작성되어야 하고, 계약 당사자가 서명하지 않는 한 구속력을 갖지 않는다"]

  result2 = []
  for i in range(len(contract_wanna_check)):
    str_ = contract_wanna_check[i]
    tmp = Contract_Model_Attention(str_)
    result_attention = tmp.create_lst()
    result2.append([str_, result_attention])

  result2
"""