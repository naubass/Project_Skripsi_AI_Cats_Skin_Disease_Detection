import tensorflow as tf

model = tf.keras.models.load_model("model_terbaik.keras", compile=False)
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

with open("model_terbaik.tflite", "wb") as f:
    f.write(tflite_model)
print("Selesai! Ukuran:", round(len(tflite_model) / 1024 / 1024, 2), "MB")