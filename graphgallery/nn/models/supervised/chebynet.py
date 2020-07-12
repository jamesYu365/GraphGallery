import tensorflow as tf
from tensorflow.keras import Model, Input
from tensorflow.keras.layers import Dropout, Softmax
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import regularizers

from graphgallery.nn.layers import ChebyConvolution
from graphgallery.sequence import FullBatchNodeSequence
from graphgallery.nn.models import SupervisedModel
from graphgallery.utils.misc import chebyshev_polynomials
from graphgallery.utils.data_utils import normalize_fn


class ChebyNet(SupervisedModel):
    """
        Implementation of Chebyshev Graph Convolutional Networks (ChebyNet). 
        [Convolutional Neural Networks on Graphs with Fast Localized Spectral Filtering](https://arxiv.org/abs/1606.09375)
        Tensorflow 1.x implementation: https://github.com/mdeff/cnn_graph, https://github.com/tkipf/gcn
        Keras implementation: https://github.com/aclyde11/ChebyGCN

        Arguments:
        ----------
            adj: shape (N, N), `scipy.sparse.csr_matrix` (or `csc_matrix`) if 
                `is_adj_sparse=True`, `np.array` or `np.matrix` if `is_adj_sparse=False`.
                The input `symmetric` adjacency matrix, where `N` is the number 
                of nodes in graph.
            x: shape (N, F), `scipy.sparse.csr_matrix` (or `csc_matrix`) if 
                `is_x_sparse=True`, `np.array` or `np.matrix` if `is_x_sparse=False`.
                The input node feature matrix, where `F` is the dimension of features.
            labels: `np.array` with shape (N,)
                The ground-truth labels for all nodes in graph.
            order (Positive integer, optional): 
                The order of Chebyshev polynomial filter. (default :obj: `2`)
            norm_adj_rate (Float scalar, optional): 
                The normalize rate for adjacency matrix `adj`. (default: :obj:`-0.5`, 
                i.e., math:: \hat{A} = D^{-\frac{1}{2}} A D^{-\frac{1}{2}}) 
            norm_x_type (String, optional): 
                How to normalize the node feature matrix. See graphgallery.utils.normalize_fn
                (default :obj: `row_wise`)
            device (String, optional): 
                The device where the model is running on. You can specified `CPU` or `GPU` 
                for the model. (default: :obj: `CPU:0`, i.e., the model is running on 
                the 0-th device `CPU`)
            seed (Positive integer, optional): 
                Used in combination with `tf.random.set_seed` & `np.random.seed` & `random.seed` 
                to create a reproducible sequence of tensors across multiple calls. 
                (default :obj: `None`, i.e., using random seed)
            name (String, optional): 
                Specified name for the model. (default: `class.__name__`)

    """

    def __init__(self, adj, x, labels, order=2, norm_adj_rate=-0.5,
                 norm_x_type='row_wise', device='CPU:0', seed=None, name=None, **kwargs):

        super().__init__(adj, x, labels,
                         device=device, seed=seed, name=name, **kwargs)

        self.order = order
        self.norm_adj_rate = norm_adj_rate
        self.norm_x_fn = normalize_fn(norm_x_type)
        self.preprocess(adj, x)

    def preprocess(self, adj, x):
        adj, x = super().preprocess(adj, x)

        if self.norm_adj_rate is not None:
            adj = chebyshev_polynomials(adj, rate=self.norm_adj_rate, order=self.order)

        if self.norm_x_fn is not None:
            x = self.norm_x_fn(x)

        with tf.device(self.device):
            self.tf_x, self.tf_adj = self.to_tensor([x, adj])

    def build(self, hiddens=[32], activations=['relu'], dropout=0.5, lr=0.01, l2_norm=5e-4, ensure_shape=True):

        assert len(hiddens) == len(activations), "The number of hidden units and " \
                                                "activation function should be the same"
        
        with tf.device(self.device):

            x = Input(batch_shape=[None, self.n_features], dtype=self.floatx, name='features')
            adj = [Input(batch_shape=[None, None],
                         dtype=self.floatx, sparse=True, name=f'adj_matrix_{i}') for i in range(self.order+1)]

            index = Input(batch_shape=[None],  dtype=self.intx, name='index')

            h = x
            for hid, activation in zip(hiddens, activations):
                h = ChebyConvolution(hid, order=self.order, activation=activation, 
                                     kernel_regularizer=regularizers.l2(l2_norm))([h, adj])
                h = Dropout(rate=dropout)(h)

            h = ChebyConvolution(self.n_classes, order=self.order)([h, adj])
            # To aviod the UserWarning of `tf.gather`, but it causes the shape 
            # of the input data to remain the same
            if ensure_shape:
                h = tf.ensure_shape(h, [self.n_nodes, self.n_classes])
            h = tf.gather(h, index)
            output = Softmax()(h)

            model = Model(inputs=[x, *adj, index], outputs=output)
            model.compile(loss='sparse_categorical_crossentropy', optimizer=Adam(lr=lr), metrics=['accuracy'])
            self.set_model(model)
            self.built = True

    def train_sequence(self, index):
        index = self.to_int(index)
        labels = self.labels[index]
        with tf.device(self.device):
            sequence = FullBatchNodeSequence([self.tf_x, *self.tf_adj, index], labels)
        return sequence

    def predict(self, index):
        super().predict(index)
        index = self.to_int(index)
        with tf.device(self.device):
            logit = self.model.predict_on_batch([self.tf_x, *self.tf_adj, index])

        if tf.is_tensor(logit):
            logit = logit.numpy()
        return logit