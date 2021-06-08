from unicodedata import ucd_3_2_0
import tensorflow as tf
import tensorflow.keras as tfk
import tensorflow.keras.layers as tfkl


def phase_invariant_cosine_squared_distance(u, v, axis):

    return 1.0 - tf.square(tf.abs(tf.reduce_sum(u * v, axis=axis)))


class PowerMean(tfk.Model):
    def __init__(self, p=-0.5, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.p = p

    def call(self, dist, axis=-1):

        dist_pow = tf.pow(dist, self.p)
        dist_pow_mean = tf.reduce_mean(dist_pow, axis=axis)
        dist_pm = tf.pow(dist_pow_mean, 1.0 / self.p)

        return dist_pm


class LehmerMean(tfk.Model):
    def __init__(self, n_freq, n_src, r=0.5, alpha=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        assert alpha >= 0.

        init_w = tf.ones(shape=(n_freq, n_src))
        self.w = tf.Variable(initial_value=init_w, trainable=True)

        self.r = r
        self.alpha = alpha

    def call(self, dist, axis=-1, eps=1e-12):

        if axis != -1:
            raise NotImplementedError

        w = tf.maximum(self.w + self.alpha, self.alpha)

        dr1 = tf.pow(tf.maximum(dist, eps), self.r - 1) * w[:, None, :]
        dr = tf.reduce_mean(dr1 * dist, axis=-1)
        dr1 = tf.reduce_mean(dr1, axis=-1)

        return dr / dr1


class DSFLoss(tfk.Model):
    def __init__(
        self,
        n_freq,
        n_chan,
        n_src,
        src_pooling_func,
        src_func_kwargs={},
        distance_func=phase_invariant_cosine_squared_distance,
        time_pooling_func=tf.reduce_mean,
        freq_pooling_func=tf.reduce_mean,
        inline_decoupling=True,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.n_freq = n_freq
        self.n_src = n_src
        self.n_chan = n_chan

        self.src_pooling_func = src_pooling_func(
            n_freq=n_freq, n_src=n_src, **src_func_kwargs
        )

        self.distance_func = distance_func
        self.time_pooling_func = time_pooling_func
        self.freq_pooling_func = freq_pooling_func

        init_mixing_matrix = tf.complex(
            tf.random.normal(
                shape=(self.n_freq, self.n_chan, self.n_src), dtype=tf.float32
            ),
            tf.random.normal(
                shape=(self.n_freq, self.n_chan, self.n_src), dtype=tf.float32
            ),
        )

        self.H = tf.Variable(initial_value=init_mixing_matrix, trainable=True)

        self.inline_decoupling = inline_decoupling

    def inline_decoupling_op(self, H):

        _, u, v = tf.linalg.svd(H, full_matrices=False)

        return tf.matmul(u, v, adjoint_b=True)

    def call(self, Xbar):

        # Xbar.shape = (n_freq, n_frames, n_chan)
        # H.shape = (n_freq, n_chan, n_src)

        if self.inline_decoupling:
            H = self.inline_decoupling_op(self.H)
        else:
            H = self.H

        Hnorm = H / tf.norm(H, axis=1, keepdims=True)

        srcframe_dist = self.distance_func(
            Hnorm[:, None, :, :], Xbar[:, :, :, None], axis=2
        )  # (n_freq, n_frames, n_src)
        frame_dist = self.src_pooling_func(
            srcframe_dist, axis=-1
        )  # (n_freq, n_frames, )
        freq_loss = self.time_pooling_func(frame_dist, axis=-1)  # (n_freq, )
        loss = self.freq_pooling_func(freq_loss, axis=-1)
        return loss


class PowerMeanDSFLoss(DSFLoss):
    def __init__(
        self,
        n_freq,
        n_chan,
        n_src,
        p=-0.5,
        distance_func=phase_invariant_cosine_squared_distance,
        time_pooling_func=tf.reduce_mean,
        freq_pooling_func=tf.reduce_sum,
        inline_decoupling=True,
        *args,
        **kwargs
    ):
        super().__init__(
            n_freq,
            n_chan,
            n_src,
            src_pooling_func=PowerMean,
            src_func_kwargs={"p": p},
            distance_func=distance_func,
            time_pooling_func=time_pooling_func,
            freq_pooling_func=freq_pooling_func,
            inline_decoupling=inline_decoupling,
            *args,
            **kwargs
        )


class LehmerMeanDSFLoss(DSFLoss):
    def __init__(
        self,
        n_freq,
        n_chan,
        n_src,
        r=0.5,
        alpha=1.0,
        distance_func=phase_invariant_cosine_squared_distance,
        time_pooling_func=tf.reduce_mean,
        freq_pooling_func=tf.reduce_mean,
        inline_decoupling=True,
        *args,
        **kwargs
    ):
        super().__init__(
            n_freq,
            n_chan,
            n_src,
            src_pooling_func=LehmerMean,
            src_func_kwargs={"r": r, "alpha": alpha},
            distance_func=distance_func,
            time_pooling_func=time_pooling_func,
            freq_pooling_func=freq_pooling_func,
            inline_decoupling=inline_decoupling,
            *args,
            **kwargs
        )