throw @"
Este agendador nao deve ser instalado na maquina local.

O processo Colaborador produtivo deve correr no servidor via systemd:

  scripts/Servidor/systemd/pastoreio-colaborador.service
  scripts/Servidor/systemd/pastoreio-colaborador.timer

Para uma execucao manual local, use apenas:

  uv --cache-dir .uv-cache run python scripts\Servidor\executar_colaborador_agendado.py

ou, depois de validar o plano, com escrita:

  uv --cache-dir .uv-cache run python scripts\Servidor\executar_colaborador_agendado.py --aplicar
"@
