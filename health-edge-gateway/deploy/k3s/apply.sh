#!/bin/bash
dir=$(cd "$(dirname "$0")" && pwd)
k3s kubectl apply -f "$dir"
