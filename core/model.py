"""
core/model.py — Loading model TFLite (sekali saja saat modul ini pertama
kali diimpor) beserta helper preprocessing gambar & inferensi.

PENTING soal urutan import: mysql.connector (via database.py) HARUS
diimpor sebelum numpy/tensorflow di suatu tempat pada proses startup
aplikasi (lihat catatan di main.py). Modul ini sendiri yang mengimpor
numpy & tensorflow, jadi main.py mengimpor mysql.connector terlebih
dahulu SEBELUM mengimpor controller mana pun yang (transitif) mengimpor
modul ini.
"""

import io
import numpy as np
from PIL import Image
import tensorflow as tf

MODEL_PATH  = "model_terbaik.tflite"
IMG_SIZE    = (224, 224)
CLASS_NAMES = ["Flea_Allergy", "Health", "Ringworm", "Scabies"]

print("Loading TFLite model...")
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()
input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()
print("TFLite model loaded!")


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize(IMG_SIZE, Image.BILINEAR)
    img_array = np.array(img, dtype=np.float32)
    img_array = img_array[..., ::-1]  # RGB -> BGR
    mean = [103.939, 116.779, 123.68]
    img_array[..., 0] -= mean[0]
    img_array[..., 1] -= mean[1]
    img_array[..., 2] -= mean[2]
    img_array = np.expand_dims(img_array, axis=0)
    return img_array


def predict_tflite(img_array: np.ndarray) -> np.ndarray:
    interpreter.set_tensor(input_details[0]['index'], img_array)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]['index'])
    return output[0]