from graphgallery.data.sequence import FullBatchSequence
from graphgallery import functional as gf
from graphgallery.gallery.nodeclas import PyTorch
from graphgallery.gallery import Trainer
from graphgallery.nn.models import get_model


@PyTorch.register()
class ChebyNet(Trainer):
    """
        Implementation of Chebyshev Graph Convolutional Networks (ChebyNet).
        `Convolutional Neural Networks on Graphs with Fast Localized Spectral Filtering <https://arxiv.org/abs/1606.09375>`
        Tensorflow 1.x implementation: <https://github.com/mdeff/cnn_graph>, <https://github.com/tkipf/gcn>
        Keras implementation: <https://github.com/aclyde11/ChebyGCN>
    """

    def data_step(self,
                  adj_transform=("cheby_basis", dict(K=2)),
                  attr_transform=None):

        graph = self.graph
        adj_matrix = gf.get(adj_transform)(graph.adj_matrix)
        attr_matrix = gf.get(attr_transform)(graph.attr_matrix)

        X, A = gf.astensors(attr_matrix, adj_matrix, device=self.data_device)

        # ``A`` and ``X`` are cached for later use
        self.register_cache(X=X, A=A)

    def model_step(self,
                   hids=[16],
                   acts=['relu'],
                   dropout=0.5,
                   weight_decay=5e-4,
                   lr=0.01,
                   bias=False):

        K = len(self.cache.A)
        model = get_model("ChebyNet", self.backend)
        model = model(self.graph.num_node_attrs,
                      self.graph.num_node_classes,
                      hids=hids,
                      acts=acts,
                      dropout=dropout,
                      K=K,
                      weight_decay=weight_decay,
                      lr=lr,
                      bias=bias)

        return model

    def train_loader(self, index):

        labels = self.graph.label[index]
        sequence = FullBatchSequence([self.cache.X, *self.cache.A],
                                     labels,
                                     out_index=index,
                                     device=self.data_device)
        return sequence