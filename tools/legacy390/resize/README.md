# Redução de resolução com CUVID legado

Scripts operacionais do IFRO. Não incluem mídia, credenciais, cópia do banco
ou arquivos de configuração do usuário. As amostras e a estrutura de teste
são privadas no servidor, sob /srv/ifro-nvidia-390/ffmpeg-full.

Para repetir na mesma estrutura, copie estes programas para
/srv/ifro-nvidia-390/resize-profile. O arquivo privado samples.json aponta para
a mídia de origem; test-media contém as amostras de H.264/HEVC. Os testes
pela API requerem um Jellyfin isolado em 127.0.0.1:18096 e a variável
JELLYFIN_API_KEY_FILE apontando para uma chave desse ambiente.

- probe.py: 600 quadros, decodificação e redução, sem codificação.
- quality.py: 180 quadros a partir de QUALITY_START (180, 480 ou 900 s),
  comparando redução CUVID com a referência CPU bicubic por SSIM/PSNR.
- transcode.py: mesmo comando HLS do Jellyfin, seleção manual dos dois caminhos.
- launcher-transcode.py: seleção automática, incluindo execução como PID 1.
- benchmark-api-command.py: ordem ABBA, duas rodadas por caminho, usando o
  comando real registrado pelo Jellyfin. O modo nativo usa a GPU na
  decodificação e a CPU na redução; o novo usa CUVID para ambas as etapas.
- fallbacks.py: 1080p preservado, saída 360p e cópia de vídeo.
- rotation.py: vídeo com rotação 90 graus encaminhado à CPU.
- validate-api.py: HLS, AAC estéreo, SRT incorporada, seek e HEVC pela CPU.

A comparação completa usou o mesmo arquivo (~31,91 s), x264 veryfast,
CRF 23, dois threads e limite de dois CPUs, com persistência NVIDIA ligada.
O checksum da amostra está em fixture.json; a amostra não é publicada.

Tempos ABBA: nativo 17,448/17,172 s; resize 12,907/13,725 s.
Médias: 17,310 -> 13,316 s (~23% menos tempo).
CPU (usuário+sistema): 28,2645 -> 24,137 s (~14,6% menos CPU adicional).
São medidas desse arquivo e hardware, sem promessa para todo conteúdo.

SSIM nas três cenas: 0,997771 / 0,997819 / 0,997673.
PSNR: 53,761 / 53,513 / 52,071 dB.
O algoritmo de redução não produz pixels idênticos ao bicubic da CPU.
A comparação de integridade anterior referia-se à decodificação sem resize.

Antes da persistência, foi observado um início de decoder de ~5 s em uma
rodada do launcher; naquela rodada o resize não ganhou no tempo total.
A persistência foi ativada antes da comparação ABBA final. Isso é uma
mudança de condição explicitamente registrada, não uma rodada descartada.
