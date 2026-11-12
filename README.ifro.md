# FFmpeg para NVIDIA Fermi / driver 390 — IFRO

Este fork contém uma adaptação experimental do **jellyfin-ffmpeg 8.1.3-2**
para decodificar H.264 em uma GeForce 610M com driver NVIDIA 390.157.
A base é o mesmo código do FFmpeg instalado no servidor Jellyfin.
Ela não é a série upstream mais nova: atualmente existe a série 9.0.

**Estado:** protótipo funcional, compilado e medido no IFRO.
A compilação completa e a integração ao Jellyfin estão em validação.
Os resultados abaixo são de decodificação/conversão, sem codificação H.264,
áudio ou reprodução de uma sessão Jellyfin completa.
A instalação Jellyfin original permanece preservada.

## O que mudou

1. Cinco funções de versões mais novas da API NVIDIA passam a ser opcionais
   no carregador de nv-codec-headers. Elas não são emuladas nem recebem
   implementações falsas. O código de decodificação usado aqui não as chama.
2. Uma ponte em C transfere os quadros para RAM fixada (pinned memory),
   sincroniza a transferência e copia os dados para os AVFrames do FFmpeg.
3. Um AVBufferPool reutiliza a RAM fixada, com uma referência exclusiva por
   transferência concorrente. Destinos maiores que o buffer reservado usam
   a alocação individual anterior. A memória é liberada no encerramento do
   contexto de quadros, enquanto o dispositivo CUDA ainda existe.
4. Instrumentação C mede as chamadas ao driver. Python executa os ensaios.

Código: [hwcontext_cuda.c](libavutil/hwcontext_cuda.c),
[legacy390_profile.h](libavutil/legacy390_profile.h),
[nvdec.c](libavcodec/nvdec.c) e [cuviddec.c](libavcodec/cuviddec.c).
Patch de cabeçalhos: [nv-codec-headers.patch](tools/legacy390/nv-codec-headers.patch).

## Ambiente validado

- HP 23-b010br; Intel Core i3-2120; 4 GB de RAM.
- GeForce 610M, arquitetura Fermi, compute capability 2.1.
- Debian 13; kernel 6.12.116+deb13-amd64; driver NVIDIA 390.157.
- NVIDIA funcional via CUDA Driver API, sem instalar o CUDA Toolkit.
- A GPU Intel integrada ainda não está disponível ao Linux neste servidor.

A GeForce 610M não tem NVENC. A adaptação não acrescenta codificação
por hardware nem decodificação HEVC/AV1 que o hardware não possua.

## Compilar o protótipo

Dependências no Debian/Ubuntu: git, build-essential, pkgconf e nasm.

```sh
git clone --branch legacy390-pinned-bridge https://github.com/franklinbaldo/jellyfin-ffmpeg.git
cd jellyfin-ffmpeg
bash tools/legacy390/build-prototype.sh
```

O script baixa nv-codec-headers n13.0.19.1, aplica o patch e compila o
protótipo em tools/legacy390/work. É possível definir LEGACY390_WORKDIR
e JOBS. Esse executável reduzido não substitui o FFmpeg completo do Jellyfin.

## Ativar a ponte somente no processo de teste

```sh
LEGACY390_PINNED_DOWNLOAD=1 LEGACY390_PINNED_POOL=1 \
tools/legacy390/work/prefix/bin/ffmpeg \
  -hwaccel cuda -hwaccel_output_format cuda -c:v h264 -i amostra.h264 \
  -vf hwdownload,format=nv12 -pix_fmt yuv420p -c:v rawvideo -f null -
```

- LEGACY390_PINNED_DOWNLOAD=1: ativa a ponte de RAM fixada.
- LEGACY390_PINNED_POOL=1: reutiliza os buffers, quando a ponte está ativa.
- LEGACY390_PROFILE=1: imprime métricas de chamadas ao driver.
- Sem essas variáveis, os caminhos experimentais ficam desativados.

O driver precisa estar acessível ao processo. Em contêineres, também são
necessários os dispositivos NVIDIA e suas bibliotecas. Este exemplo não
expõe o servidor Jellyfin nem suas credenciais.

## Resultados medidos

Mesmo trecho H.264 1080p, saída rawvideo YUV420P descartada, dois threads.
Os testes de vazão não calculam SHA256 a cada quadro.

| Quadros | CPU | NVIDIA com ponte, antes do pool |
|---:|---:|---:|
| 300 | 4,153 s | 3,762 s |
| 3.000 | 36,633 s | 29,469 s |
| 9.000 | 110,718 s | 89,025 s |

Com reutilização dos buffers, os 9.000 quadros levaram **77,114 s**,
com aproximadamente 120–130 quadros/s depois do trecho inicial.
Houve uma alocação e uma liberação de RAM fixada, em lugar de 9.000 de cada.
O custo dessas chamadas caiu de aproximadamente 31,7 s para 3,6 ms.
Isso não equivale a economizar 31,7 s no tempo total: outras esperas e
sobreposições entre as etapas também mudam.

A integridade foi verificada separadamente: 180 quadros distintos tiveram
SHA256 idêntico entre CPU, CUVID e NVDEC com pool. Os 9.000 quadros foram
contados e concluídos sem erro, mas não comparados individualmente por hash.

Dados: [perfil longo](tools/legacy390/long-profile-results.json) e
[perfil com pool](tools/legacy390/pool-profile-results.json).
Scripts e detalhes: [tools/legacy390](tools/legacy390/README.md).

## Warm-up e limites das medições

CUDA normalmente levou cerca de 0,4 s para iniciar; o decodificador levou
cerca de 0,33 s em várias rodadas e cerca de 5 s em algumas outras.
As amostras longas reduzem o peso desse início, mas a vazão estabiliza;
ela não aumenta indefinidamente com o número de quadros.

As cenas têm complexidade variável e o servidor manteve outros serviços
ativos. Os intervalos de vazão interpolam progresso coletado a cada 250 ms.
Métricas de chamadas de threads diferentes se sobrepõem e não devem ser
somadas como etapas independentes. Uma chamada de transferência também
pode esperar trabalho anterior da GPU.

## Compilação completa e integração

[build-full.sh](tools/legacy390/build-full.sh) contém a receita em teste.
Ela é executada em um contêiner Ubuntu compatível com a imagem Jellyfin
instalada, com volumes /src (este código), /headers (cabeçalhos já
corrigidos) e /work (diretório de compilação). Produz /work/install/opt/ifro-ffmpeg.

A receita habilita os codecs e protocolos nativos, x264/x265, dav1d, VPx,
áudio, libass/legendas, HLS, HTTPS e VA-API/CUDA/CUVID/NVDEC.
Ela não reproduz todos os backends opcionais da imagem oficial:
CUDA-LLVM, Vulkan/libplacebo, AMF, QSV/oneVPL, SVT-AV1 e FDK-AAC não estão
habilitados. A presença do encoder NVENC na lista não significa que a
GeForce 610M possa usá-lo.

A ativação no Jellyfin depende de validação da sessão completa, com
codificação por CPU, áudio, legendas, busca no vídeo e retorno seguro ao
executável original. Não usar os números do protótipo como promessa de
velocidade da transcodificação completa.

## Fontes e manutenção

- [Jellyfin: aceleração de hardware](https://jellyfin.org/docs/general/post-install/transcoding/hardware-acceleration/)
- [Intel: VA-API](https://www.intel.com/content/www/us/en/developer/articles/technical/linuxmedia-vaapi.html)
- [FFmpeg: versões](https://ffmpeg.org/download.html)
- [Cabeçalhos NVIDIA usados pelo FFmpeg](https://github.com/FFmpeg/nv-codec-headers)

Este fork preserva as licenças do FFmpeg. Scripts de medição não incluem
mídia, chaves de API, credenciais ou configurações privadas do Jellyfin.
Não altera o driver do sistema nem as opções de BIOS.
