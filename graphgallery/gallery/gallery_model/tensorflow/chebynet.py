import tensorflow as tf

from graphgallery.gallery import GalleryModel
from graphgallery.sequence import FullBatchNodeSequence

from graphgallery.nn.models.tensorflow import ChebyNet as tfChebyNet

from graphgallery import functional as gf


class ChebyNet(GalleryModel):
    """
        Implementation of Chebyshev Graph Convolutional Networks (ChebyNet).
        `Convolutional Neural Networks on Graphs with Fast Localized Spectral Filtering <https://arxiv.org/abs/1606.09375>`
        Tensorflow 1.x implementation: <https://github.com/mdeff/cnn_graph>, <https://github.com/tkipf/gcn>
        Keras implementation: <https://github.com/aclyde11/ChebyGCN>

    """

    def __init__(self,
                 *graph,
                 adj_transform="cheby_basis",
                 attr_transform=None,
                 device='cpu:0',
                 seed=None,
                 name=None,
                 **kwargs):
        r"""Create a ChebyNet model.

        This can be instantiated in several ways:

            model = ChebyNet(graph)
                with a `graphgallery.data.Graph` instance representing
                A sparse, attributed, labeled graph.

            model = ChebyNet(adj_matrix, node_attr, labels)
                where `adj_matrix` is a 2D Scipy sparse matrix denoting the graph,
                 `node_attr` is a 2D Numpy array-like matrix denoting the node 
                 attributes, `labels` is a 1D Numpy array denoting the node labels.

        Parameters:
        ----------
        graph: An instance of `graphgallery.data.Graph` or a tuple (list) of inputs.
            A sparse, attributed, labeled graph.
        adj_transform: string, `transform`, or None. optional
            How to transform the adjacency matrix. See `graphgallery.functional`
            (default: :obj:`'cheby_basis'`) 
        attr_transform: string, `transform`, or None. optional
            How to transform the node attribute matrix. See `graphgallery.functional`
            (default :obj: `None`)
        device: string. optional
            The device where the model is running on. You can specified `CPU` or `GPU`
            for the model. (default: :str: `CPU:0`, i.e., running on the 0-th `CPU`)
        seed: interger scalar. optional 
            Used in combination with `tf.random.set_seed` & `np.random.seed` 
            & `random.seed` to create a reproducible sequence of tensors across 
            multiple calls. (default :obj: `None`, i.e., using random seed)
        name: string. optional
            Specified name for the model. (default: :str: `class.__name__`)
        kwargs: other custom keyword parameters.

        """
        super().__init__(*graph, device=device, seed=seed, name=name, **kwargs)

        self.adj_transform = gf.get(adj_transform)
        self.attr_transform = gf.get(attr_transform)
        self.process()

    def process_step(self):
        graph = self.graph
        adj_matrix = self.adj_transform(graph.adj_matrix)
        node_attr = self.attr_transform(graph.node_attr)

        self.feature_inputs, self.structure_inputs = gf.astensors(
            node_attr, adj_matrix, device=self.device)

    # use decorator to make sure all list arguments have the same length
    @gf.equal()
    def build(self,
              hiddens=[16],
              activations=['relu'],
              dropout=0.5,
              weight_decay=5e-4,
              lr=0.01,
              use_bias=False):

        if self.backend == "tensorflow":
            with tf.device(self.device):
                self.model = tfChebyNet(self.graph.num_node_attrs,
                                        self.graph.num_node_classes,
                                        hiddens=hiddens,
                                        activations=activations,
                                        dropout=dropout,
                                        weight_decay=weight_decay,
                                        order=self.adj_transform.order,
                                        lr=lr,
                                        use_bias=use_bias)
        else:
            raise NotImplementedError

    def train_sequence(self, index):

        labels = self.graph.node_label[index]
        sequence = FullBatchNodeSequence(
            [self.feature_inputs, *self.structure_inputs, index],
            labels,
            device=self.device)
        return sequence