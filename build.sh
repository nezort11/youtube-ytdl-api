#!/bin/bash
set -e

echo "📦 Installing dependencies..."
mkdir -p ./build
./.venv/bin/pip install -r requirements.txt --target ./build

echo "🧱 Copying source files..."
cp *.py build/

# Bundle Deno binary (required for YouTube JS challenge solving)
# We check if it already exists in build/ to avoid redundant downloads.
DENO_VERSION="v2.2.3"
if [ ! -f "./build/deno" ]; then
    echo "🦕 Deno binary not found in build folder. Downloading $DENO_VERSION for Linux x64..."
    curl -L "https://github.com/denoland/deno/releases/download/${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip" -o ./build/deno.zip
    unzip -o ./build/deno.zip -d ./build/
    rm ./build/deno.zip
    chmod +x ./build/deno
else
    echo "🦕 Deno binary already exists in build folder, skipping download."
fi

echo "🧩 Creating zip..."
cd build
zip -r ../ytdl-function.zip .
cd ..

echo "✅ Done"
