import tensorflow as tf
from tensorflow.keras import layers, Model
import numpy as np

class MobileNetSimilarityModel:
    def __init__(self, input_shape=(224, 224, 3), embedding_dim=512):
        self.input_shape = input_shape
        self.embedding_dim = embedding_dim
        self.model = self._build_model()
    
    def _build_model(self):
        base_model = tf.keras.applications.MobileNetV3Large(
            input_shape=self.input_shape,
            include_top=False,
            weights='imagenet',
            pooling='avg'
        )
        
        base_model.trainable = False
        
        inputs = tf.keras.Input(shape=self.input_shape)
        
        x = tf.keras.applications.mobilenet_v3.preprocess_input(inputs)
        
        x = base_model(x, training=False)
        
        x = layers.Dense(self.embedding_dim, activation=None, name='embedding')(x)
        x = layers.Lambda(lambda t: tf.nn.l2_normalize(t, axis=1), name='l2_normalize')(x)
        
        model = Model(inputs, x, name='mobilenet_similarity')
        
        return model
    
    def get_embeddings(self, images):
        return self.model.predict(images, batch_size=1)
    
    def save_for_tflite(self, filepath):
        self.model.export(filepath)
    
    def summary(self):
        return self.model.summary()