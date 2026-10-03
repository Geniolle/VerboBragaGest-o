# Diagnóstico do Timer - Pastoreio Colaborador

**Data:** 2026-10-03  
**Problema:** Timer não executou desde 2026-09-22 (11 dias)  
**Registo Pendente:** Cleitinho Fubá (Linha 38 em Membresia)  

---

## Última Execução Conhecida

```
Data/Hora: 2026-09-22T06:56:41+01:00
Exit Code: 0 (sucesso)
Duração: 22.59 segundos
Tempo Total de Tarefas: 22.38 segundos
```

**Etapas Executadas:**
1. Analisar pendentes Membresia → BP SERVICE: 02.44s
2. Marcar pendentes: 02.69s
3. Validar departamentos: 03.68s
4. Atualizar BP COLABORADOR: 04.04s
5. Atualizar BP AUTORITY: 02.54s
6. Reconciliar BP AUTORITY: 02.59s
7. Sincronizar → BP ALGORITIMO: 04.39s

---

## Verificações a Fazer NO SERVIDOR

Execute os seguintes comandos para diagnosticar:

### 1. Status Atual do Timer

```bash
systemctl status pastoreio-colaborador.timer
```

**O que procurar:**
- `active (running)` = Timer está ativo ✅
- `inactive (dead)` = Timer está parado ❌
- `enabled` = Inicia automaticamente após reboot ✅
- `disabled` = Não inicia automaticamente ❌

---

### 2. Verificar se Timer está Habilitado

```bash
systemctl is-enabled pastoreio-colaborador.timer
```

**Resultado esperado:**
- `enabled` = OK ✅
- `disabled` = Problema ❌

---

### 3. Ver o Lock File Atual

```bash
cat /home/opc/pastoreio-orquestrador/runtime/colaborador.lock 2>/dev/null || echo "Sem lock file"
```

**Se houver lock file:**
- Verificar se o PID ainda está a rodar: `ps -p <PID>`
- Se não estiver: Lock está corrompido e precisa limpeza

---

### 4. Ver o Último Log (existe e está documentado)

```bash
tail -20 /home/opc/pastoreio-orquestrador/runtime/colaborador_ultimo.log
```

**Resultado esperado:** Deve mostrar 22 de Setembro de 2026

---

### 5. Ver Logs do Systemd (últimos 24 horas)

```bash
journalctl -u pastoreio-colaborador.service -n 100 --no-pager
```

**O que procurar:**
- Erros depois de 22 SET
- Sinais de falha
- Timeout messages

---

### 6. Listar Timers Activos

```bash
systemctl list-timers pastoreio-colaborador.timer
```

**O que procurar:**
- NEXT: quando será a próxima execução
- LAST: quando foi a última (deve ser recente)

---

## Possíveis Causas e Soluções

### Causa A: Timer Desativado

```bash
# Reativar
sudo systemctl enable pastoreio-colaborador.timer
sudo systemctl start pastoreio-colaborador.timer

# Verificar
systemctl status pastoreio-colaborador.timer
```

---

### Causa B: Lock File Corrompido

```bash
# Verificar lock file
ls -la /home/opc/pastoreio-orquestrador/runtime/colaborador.lock

# Se existe mas processo não está vivo:
rm /home/opc/pastoreio-orquestrador/runtime/colaborador.lock

# Reiniciar timer
sudo systemctl restart pastoreio-colaborador.timer
```

---

### Causa C: Servidor Reiniciado

```bash
# Verificar data/hora do sistema
date

# Verificar uptime do servidor
uptime

# Se reboot recente: timer pode ter sido interrompido
# Solução: reiniciar o timer
sudo systemctl restart pastoreio-colaborador.timer
```

---

### Causa D: Erro Silencioso no Systemd

```bash
# Listar todas as falhas de timer
systemctl list-timers --failed

# Ver logs com mais contexto
journalctl -u pastoreio-colaborador.service -u pastoreio-colaborador.timer -n 200 --no-pager
```

---

## Validação Após Correção

Depois de aplicar qualquer solução:

```bash
# 1. Confirmar que timer está activo
systemctl status pastoreio-colaborador.timer

# 2. Confirmar que timer está habilitado
systemctl is-enabled pastoreio-colaborador.timer

# 3. Aguardar ~1 minuto para próxima execução
sleep 60

# 4. Verificar se executou
tail -20 /home/opc/pastoreio-orquestrador/runtime/colaborador_ultimo.log

# 5. Confirmar que há novo timestamp
date

# 6. Verificar se registou nova execução
journalctl -u pastoreio-colaborador.service -n 10 --no-pager
```

---

## Checklist de Execução

- [ ] Executar verificação 1: `systemctl status pastoreio-colaborador.timer`
- [ ] Executar verificação 2: `systemctl is-enabled pastoreio-colaborador.timer`
- [ ] Executar verificação 3: Verificar lock file
- [ ] Executar verificação 4: Verificar último log (data 22 SET?)
- [ ] Executar verificação 5: Ver logs systemd
- [ ] Executar verificação 6: Listar timers
- [ ] Identificar causa
- [ ] Aplicar solução
- [ ] Validar que está a rodar
- [ ] Confirmar nova execução após ~1 minuto

---

## Resultado Esperado

**Quando timer está funcionando:**
```
Cleitinho Fubá (Membresia linha 38):
├─ BP SERVICE: será marcado como TRUE ✅
├─ ID_USER: será criado como 122 ✅
└─ TIMESTAMP: será preenchido automaticamente ✅
```

**Periodocidade:** A cada 1 minuto
