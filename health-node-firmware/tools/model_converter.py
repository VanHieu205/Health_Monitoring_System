# Convert quantized .tflite to C header array
import sys
import subprocess

def convert(tflite_path, output_header):
    cmd = f"xxd -i {tflite_path} > {output_header}"
    subprocess.run(cmd, shell=True)
    print(f"Model converted to {output_header}")
