In my a1 folder, I have two folders 'bert' and 'distilbert'. Each model is in its specified folder. Inside the those folders are the scripts of the model, the data, the evaluation script, and the output prediction files. You can disregard the 'other' folder.




To run the model:
python3 nlp_244_bert_multi.py
or
python3 nlp_244_distilbert_multi.py


These two scripts will each output three txt files.
1)	hw1_labels_dev.txt	(My gold labels for train/test split)
2)	prediction_dev.txt	(My prediction on my test split)
3)	submission.txt		(My precition for the test data)


The (1) and (2) were used for development and fine-tuning.

(3) is the actually submission, the prediction of the test set.


To run evaluation:
python3 evaluation_2.py 	(I used this one for my results)
or
python3 evaluation.py