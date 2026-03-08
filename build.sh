#!/bin/bash
set -e

echo "📦 Installing dependencies..."
mkdir -p ./build
./.venv/bin/pip install -r requirements.txt --target ./build

echo "🧱 Copying source files..."
cp *.py build/

echo "🧩 Creating zip..."
cd build
zip -r ../ytdl-function.zip .
cd ..

echo "✅ Done"
