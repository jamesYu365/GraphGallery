#!/usr/bin/env python
# coding: utf-8

import torch
import graphgallery

print("GraphGallery version: ", graphgallery.__version__)
print("Torch version: ", torch.__version__)

'''
Load Datasets
- cora/citeseer/pubmed
'''
from graphgallery.datasets import NPZDataset
data = NPZDataset('cora', root="~/GraphData/datasets/", verbose=False, transform='standardize')
graph = data.graph
splits = data.split_nodes(random_state=15)

graphgallery.set_backend("pytorch")

from graphgallery.gallery.nodeclas import TrimmedGCN
trainer = TrimmedGCN(device="gpu", seed=123).setup_graph(graph).build()
trainer.fit(splits.train_nodes, splits.val_nodes, verbose=1, epochs=100)
results = trainer.evaluate(splits.test_nodes)
print(f'Test loss {results.loss:.5}, Test accuracy {results.accuracy:.2%}')