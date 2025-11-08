%prep
# Fonte do Ollama (Source0)
%forgesetup

# Fonte do OllamaGrid (Source1) -> ./ollama-grid-%{gridcommit}
%setup -q -T -D -a 1

# Duplica a árvore para cada backend
cp -a . ../ollama-0.12.9-vulkan
cp -a . ../ollama-0.12.9-rocm6
cp -a . ../ollama-0.12.9-cuda-12.9

# Copia scripts e patch do Source1 para dentro da árvore CUDA 12.9
install -d ../ollama-0.12.9-cuda-12.9/tools

# apply (caminho que você definiu)
cp -a ollama-grid-%{gridcommit}/scripts/apply-cuda129-patch.sh \
      ../ollama-0.12.9-cuda-12.9/tools/

# revert (assumindo mesmo diretório 'scripts/')
if [ -f ollama-grid-%{gridcommit}/scripts/revert-cuda129-patch.sh ]; then
  cp -a ollama-grid-%{gridcommit}/scripts/revert-cuda129-patch.sh \
        ../ollama-0.12.9-cuda-12.9/tools/
fi

# patch — tenta primeiro em patches/, depois em scripts/ (fallback)
if [ -f ollama-grid-%{gridcommit}/patches/cuda129.patch ]; then
  cp -a ollama-grid-%{gridcommit}/patches/cuda129.patch \
        ../ollama-0.12.9-cuda-12.9/tools/
elif [ -f ollama-grid-%{gridcommit}/scripts/cuda129.patch ]; then
  cp -a ollama-grid-%{gridcommit}/scripts/cuda129.patch \
        ../ollama-0.12.9-cuda-12.9/tools/
else
  echo "ERRO: cuda129.patch não encontrado em patches/ ou scripts/ do Source1" >&2
  exit 1
fi

chmod +x ../ollama-0.12.9-cuda-12.9/tools/apply-cuda129-patch.sh || :
chmod +x ../ollama-0.12.9-cuda-12.9/tools/revert-cuda129-patch.sh || :
