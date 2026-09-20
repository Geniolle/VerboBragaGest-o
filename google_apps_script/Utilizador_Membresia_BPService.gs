/**
 * Processo Utilizador / Subprocesso: Criar no utilizador Membresia.
 *
 * Sincroniza a sheet "Membresia" com "BP SERVICE".
 *
 * DRY_RUN=true analisa e registra no Logger tudo que seria feito, sem
 * escrever nas sheets. Só altere para false depois de validar o relatório.
 */
const MEMBRESIA_BP_CONFIG = {
  DRY_RUN: true,
  SHEET_MEMBRESIA: 'Membresia',
  SHEET_BP_SERVICE: 'BP SERVICE',
  FLAG_PROCESSADO: 'BP SERVICE',
  LOG_PREFIX: '[MEMBRESIA-BP]'
};

const MEMBRESIA_COLS = {
  NOME: 'Nome Próprio + Apelido',
  DATA_NASCIMENTO: 'Data de Nascimento',
  EMAIL: 'Email',
  TELEFONE: 'Contacto Telefónico',
  TEM_WHATSAPP: 'O número acima tem WhatsApp',
  NUMBER_WHATSAPP: 'Nº WhatsApp',
  CODIGO_POSTAL: 'Código Postal',
  MORADA: 'Morada',
  FREGUESIA: 'Freguesia',
  DISCIPULADO: 'Discipulado Verbo da Vida',
  FLAG_BP_SERVICE: 'BP SERVICE'
};

const BP_SERVICE_COLS = {
  ID_USER: 'ID_USER',
  NOME: 'NOME',
  DATA_NASCIMENTO: 'DATA NASCIMENTO',
  EMAIL: 'EMAIL',
  TELEFONE: 'TELEFONE',
  WHATSAPP: 'WHATSAPP',
  NUMBER_WHATSAPP: 'NUMBER_WHATSAPP',
  CODIGO_POSTAL: 'CÓDIGO POSTAL',
  MORADA: 'MORADA',
  FREGUESIA: 'FREGUESIA',
  DISCIPULADO: 'DISCIPULADO VERBO DA VIDA'
};

function sincronizarMembresiaComBPService() {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheetMembresia = ss.getSheetByName(MEMBRESIA_BP_CONFIG.SHEET_MEMBRESIA);
    const sheetBpService = ss.getSheetByName(MEMBRESIA_BP_CONFIG.SHEET_BP_SERVICE);

    if (!sheetMembresia) {
      throw new Error(`Sheet "${MEMBRESIA_BP_CONFIG.SHEET_MEMBRESIA}" não encontrada.`);
    }
    if (!sheetBpService) {
      throw new Error(`Sheet "${MEMBRESIA_BP_CONFIG.SHEET_BP_SERVICE}" não encontrada.`);
    }

    const membresiaValues = sheetMembresia.getDataRange().getValues();
    const bpValues = sheetBpService.getDataRange().getValues();

    if (membresiaValues.length < 1 || bpValues.length < 1) {
      throw new Error('Membresia e BP SERVICE precisam ter cabeçalho.');
    }

    const membresiaHeaders = mapHeaders(membresiaValues[0]);
    const bpHeaders = mapHeaders(bpValues[0]);

    validateRequiredHeaders_(membresiaHeaders, Object.values(MEMBRESIA_COLS), 'Membresia');
    validateRequiredHeaders_(bpHeaders, Object.values(BP_SERVICE_COLS), 'BP SERVICE');

    const bpIndexes = buildBpIndexes(bpValues, bpHeaders);
    const nextIdState = {
      nextId: generateNextUserId(bpValues, bpHeaders),
      usedIds: collectExistingNumericIds_(bpValues, bpHeaders)
    };

    const stats = {
      pendentes: 0,
      encontrados: 0,
      criados: 0,
      ambiguos: 0,
      erros: 0
    };

    const encontrados = [];
    const criados = [];
    const ambiguos = [];
    const erros = [];
    const flagUpdates = [];
    const newRows = [];
    const bpRowsInMemory = bpValues.slice();

    const pendentes = [];
    for (let i = 1; i < membresiaValues.length; i++) {
      const row = membresiaValues[i];
      const flag = getCell_(row, membresiaHeaders, MEMBRESIA_COLS.FLAG_BP_SERVICE);
      if (isTruthy(flag)) {
        continue;
      }
      if (!isBlank_(flag)) {
        logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX}[IGNORADO] Linha=${i + 1} BP SERVICE não está vazio: ${flag}`);
        continue;
      }
      pendentes.push({ rowIndex: i + 1, row });
    }

    stats.pendentes = pendentes.length;
    logLine_('###############################################################################');
    logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX} INÍCIO`);
    logLine_(`DRY_RUN: ${MEMBRESIA_BP_CONFIG.DRY_RUN}`);
    logLine_(`Pendentes: ${stats.pendentes}`);
    logLine_('###############################################################################');

    pendentes.forEach(item => {
      const linhaSheet = item.rowIndex;
      const row = item.row;
      const nome = String(getCell_(row, membresiaHeaders, MEMBRESIA_COLS.NOME) || '').trim();

      try {
        const match = findExistingBpUser(row, membresiaHeaders, bpIndexes);

        if (match.status === 'found') {
          stats.encontrados++;
          encontrados.push({
            linha: linhaSheet,
            nome,
            idUser: match.user.idUser,
            metodo: match.method
          });
          flagUpdates.push({ row: linhaSheet, value: true });
          logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX}[ENCONTRADO] Linha=${linhaSheet} Nome=${nome} ID_USER=${match.user.idUser} Metodo=${match.method}`);
          return;
        }

        if (match.status === 'ambiguous') {
          stats.ambiguos++;
          const possibleIds = match.candidates.map(c => c.idUser).filter(String);
          ambiguos.push({
            linha: linhaSheet,
            nome,
            motivo: match.reason,
            ids: possibleIds
          });
          logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX}[AMBIGUO]`);
          logLine_(`Linha Membresia: ${linhaSheet}`);
          logLine_(`Nome: ${nome}`);
          logLine_(`Motivo: ${match.reason}`);
          logLine_(`Possíveis ID_USER: ${possibleIds.join(', ')}`);
          return;
        }

        const newId = allocateNextUserId_(nextIdState);
        const newRow = buildNewBpRow(row, membresiaHeaders, bpValues[0], bpHeaders, newId);

        if (idExistsInRows_(bpRowsInMemory, bpHeaders, newId)) {
          throw new Error(`ID_USER ${newId} já existe antes da gravação.`);
        }

        bpRowsInMemory.push(newRow);
        addBpUserToIndexes_(bpIndexes, parseBpUser_(newRow, bpHeaders, bpRowsInMemory.length));
        newRows.push(newRow);
        criados.push({ linha: linhaSheet, nome, idUser: newId });
        flagUpdates.push({ row: linhaSheet, value: true });
        stats.criados++;
        logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX}[CRIADO] Linha=${linhaSheet} Nome=${nome} ID_USER=${newId}`);
      } catch (error) {
        stats.erros++;
        erros.push({ linha: linhaSheet, nome, erro: error.message });
        logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX}[ERRO] Linha=${linhaSheet} Nome=${nome} Erro=${error.message}`);
      }
    });

    if (!MEMBRESIA_BP_CONFIG.DRY_RUN) {
      applyMembresiaBpChanges_(sheetMembresia, sheetBpService, membresiaHeaders, flagUpdates, newRows);
    }

    logDryRunDetails_(encontrados, criados, ambiguos, erros, flagUpdates, newRows);
    logLine_('###############################################################################');
    logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX} RESUMO`);
    logLine_(`Pendentes analisados: ${stats.pendentes}`);
    logLine_(`Já existentes: ${stats.encontrados}`);
    logLine_(`Criados: ${stats.criados}`);
    logLine_(`Ambíguos: ${stats.ambiguos}`);
    logLine_(`Erros: ${stats.erros}`);
    logLine_('###############################################################################');
  } finally {
    lock.releaseLock();
  }
}

function mapHeaders(headerRow) {
  const headers = {};
  headerRow.forEach((header, index) => {
    const key = String(header || '').trim();
    if (key) {
      headers[key] = index;
    }
  });
  return headers;
}

function validateRequiredHeaders_(headers, required, sheetName) {
  const missing = required.filter(name => headers[name] === undefined);
  if (missing.length > 0) {
    throw new Error(`Sheet "${sheetName}" sem coluna(s): ${missing.join(', ')}`);
  }
}

function getCell_(row, headers, colName) {
  const index = headers[colName];
  if (index === undefined || index >= row.length) {
    return '';
  }
  return row[index];
}

function setCell_(row, headers, colName, value) {
  const index = headers[colName];
  if (index !== undefined) {
    row[index] = value;
  }
}

function normalizeText(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value)
    .replace(/[\u200B-\u200D\uFEFF]/g, '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toUpperCase()
    .replace(/\s+/g, ' ');
}

function normalizeEmail(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value).trim().toLowerCase();
}

function normalizePhone(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value).replace(/\D+/g, '');
}

function normalizeDate(value) {
  if (value === null || value === undefined || value === '') {
    return '';
  }

  if (Object.prototype.toString.call(value) === '[object Date]' && !isNaN(value.getTime())) {
    return Utilities.formatDate(value, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  }

  const text = String(value).trim();
  if (!text) {
    return '';
  }

  const datePart = text.split(' ')[0];
  let match = datePart.match(/^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})$/);
  if (match) {
    return `${match[1]}-${pad2_(match[2])}-${pad2_(match[3])}`;
  }

  match = datePart.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})$/);
  if (match) {
    return `${match[3]}-${pad2_(match[2])}-${pad2_(match[1])}`;
  }

  const parsed = new Date(text);
  if (!isNaN(parsed.getTime())) {
    return Utilities.formatDate(parsed, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  }

  return '';
}

function pad2_(value) {
  return String(value).padStart(2, '0');
}

function isTruthy(value) {
  if (value === true) {
    return true;
  }
  return normalizeText(value) === 'TRUE';
}

function isBlank_(value) {
  return value === null || value === undefined || String(value).trim() === '';
}

function parseWhatsApp(value) {
  const text = normalizeText(value);
  if (text === 'SIM') {
    return true;
  }
  if (text === 'NAO' || text === 'NÃO') {
    return false;
  }
  return null;
}

function buildBpIndexes(bpValues, bpHeaders) {
  const users = [];
  const byEmail = {};
  const byPhone = {};
  const byNameBirth = {};

  for (let i = 1; i < bpValues.length; i++) {
    const user = parseBpUser_(bpValues[i], bpHeaders, i + 1);
    users.push(user);
    addToIndex_(byEmail, user.email, user);
    user.phones.forEach(phone => addToIndex_(byPhone, phone, user));
    addToIndex_(byNameBirth, user.nameBirthKey, user);
  }

  return { users, byEmail, byPhone, byNameBirth };
}

function parseBpUser_(row, bpHeaders, rowIndex) {
  const telefone = normalizePhone(getCell_(row, bpHeaders, BP_SERVICE_COLS.TELEFONE));
  const numberWhatsApp = normalizePhone(getCell_(row, bpHeaders, BP_SERVICE_COLS.NUMBER_WHATSAPP));
  const phones = uniqueNonEmpty_([telefone, numberWhatsApp]);
  const name = normalizeText(getCell_(row, bpHeaders, BP_SERVICE_COLS.NOME));
  const birth = normalizeDate(getCell_(row, bpHeaders, BP_SERVICE_COLS.DATA_NASCIMENTO));

  return {
    rowIndex,
    idUser: String(getCell_(row, bpHeaders, BP_SERVICE_COLS.ID_USER) || '').trim(),
    name,
    birth,
    email: normalizeEmail(getCell_(row, bpHeaders, BP_SERVICE_COLS.EMAIL)),
    telefone,
    numberWhatsApp,
    phones,
    nameBirthKey: name && birth ? `${name}|${birth}` : ''
  };
}

function addBpUserToIndexes_(indexes, user) {
  indexes.users.push(user);
  addToIndex_(indexes.byEmail, user.email, user);
  user.phones.forEach(phone => addToIndex_(indexes.byPhone, phone, user));
  addToIndex_(indexes.byNameBirth, user.nameBirthKey, user);
}

function addToIndex_(index, key, user) {
  if (!key) {
    return;
  }
  if (!index[key]) {
    index[key] = [];
  }
  index[key].push(user);
}

function findExistingBpUser(membresiaRow, membresiaHeaders, bpIndexes) {
  const memb = parseMembresiaIdentity_(membresiaRow, membresiaHeaders);

  if (memb.email) {
    const emailCandidates = bpIndexes.byEmail[memb.email] || [];
    const emailResult = resolveCandidates_(emailCandidates, memb, 'EMAIL', 'email partilhado sem confirmação suficiente');
    if (emailResult.status !== 'none') {
      return emailResult;
    }
  }

  const phoneCandidates = [];
  memb.phones.forEach(phone => {
    (bpIndexes.byPhone[phone] || []).forEach(user => phoneCandidates.push(user));
  });
  const uniquePhoneCandidates = uniqueUsers_(phoneCandidates);
  if (uniquePhoneCandidates.length === 1) {
    return { status: 'found', user: uniquePhoneCandidates[0], method: 'TELEFONE' };
  }
  if (uniquePhoneCandidates.length > 1) {
    return {
      status: 'ambiguous',
      candidates: uniquePhoneCandidates,
      reason: 'telefone/whatsapp partilhado sem confirmação suficiente'
    };
  }

  if (memb.nameBirthKey) {
    const nameBirthCandidates = bpIndexes.byNameBirth[memb.nameBirthKey] || [];
    if (nameBirthCandidates.length === 1) {
      return { status: 'found', user: nameBirthCandidates[0], method: 'NOME+DATA_NASCIMENTO' };
    }
    if (nameBirthCandidates.length > 1) {
      return {
        status: 'ambiguous',
        candidates: nameBirthCandidates,
        reason: 'nome + data de nascimento com múltiplos registos'
      };
    }
  }

  return { status: 'none' };
}

function parseMembresiaIdentity_(row, headers) {
  const telefone = normalizePhone(getCell_(row, headers, MEMBRESIA_COLS.TELEFONE));
  const numberWhatsApp = normalizePhone(getCell_(row, headers, MEMBRESIA_COLS.NUMBER_WHATSAPP));
  const name = normalizeText(getCell_(row, headers, MEMBRESIA_COLS.NOME));
  const birth = normalizeDate(getCell_(row, headers, MEMBRESIA_COLS.DATA_NASCIMENTO));

  return {
    name,
    birth,
    email: normalizeEmail(getCell_(row, headers, MEMBRESIA_COLS.EMAIL)),
    telefone,
    numberWhatsApp,
    phones: uniqueNonEmpty_([telefone, numberWhatsApp]),
    nameBirthKey: name && birth ? `${name}|${birth}` : ''
  };
}

function resolveCandidates_(candidates, memb, baseMethod, ambiguousReason) {
  const unique = uniqueUsers_(candidates);
  if (unique.length === 0) {
    return { status: 'none' };
  }
  if (unique.length === 1) {
    return { status: 'found', user: unique[0], method: baseMethod };
  }

  const byTelefone = memb.telefone ? unique.filter(user => user.phones.indexOf(memb.telefone) >= 0) : [];
  if (byTelefone.length === 1) {
    return { status: 'found', user: byTelefone[0], method: `${baseMethod}+TELEFONE` };
  }

  const byNumberWhatsApp = memb.numberWhatsApp ? unique.filter(user => user.phones.indexOf(memb.numberWhatsApp) >= 0) : [];
  if (byNumberWhatsApp.length === 1) {
    return { status: 'found', user: byNumberWhatsApp[0], method: `${baseMethod}+NUMBER_WHATSAPP` };
  }

  const byNameBirth = memb.nameBirthKey ? unique.filter(user => user.nameBirthKey === memb.nameBirthKey) : [];
  if (byNameBirth.length === 1) {
    return { status: 'found', user: byNameBirth[0], method: `${baseMethod}+NOME+DATA_NASCIMENTO` };
  }

  return { status: 'ambiguous', candidates: unique, reason: ambiguousReason };
}

function uniqueUsers_(users) {
  const seen = {};
  const result = [];
  users.forEach(user => {
    const key = user.idUser || `row:${user.rowIndex}`;
    if (!seen[key]) {
      seen[key] = true;
      result.push(user);
    }
  });
  return result;
}

function uniqueNonEmpty_(values) {
  const seen = {};
  const result = [];
  values.forEach(value => {
    if (value && !seen[value]) {
      seen[value] = true;
      result.push(value);
    }
  });
  return result;
}

function generateNextUserId(bpValues, bpHeaders) {
  const ids = collectExistingNumericIds_(bpValues, bpHeaders);
  const maxId = ids.reduce((max, id) => Math.max(max, id), 0);
  return maxId + 1;
}

function collectExistingNumericIds_(bpValues, bpHeaders) {
  const ids = [];
  for (let i = 1; i < bpValues.length; i++) {
    const raw = String(getCell_(bpValues[i], bpHeaders, BP_SERVICE_COLS.ID_USER) || '').trim();
    if (!/^\d+$/.test(raw)) {
      continue;
    }
    ids.push(Number(raw));
  }
  return ids;
}

function allocateNextUserId_(state) {
  while (state.usedIds.indexOf(state.nextId) >= 0) {
    state.nextId++;
  }
  const allocated = state.nextId;
  state.usedIds.push(allocated);
  state.nextId++;
  return allocated;
}

function idExistsInRows_(bpRows, bpHeaders, idUser) {
  const target = String(idUser);
  for (let i = 1; i < bpRows.length; i++) {
    if (String(getCell_(bpRows[i], bpHeaders, BP_SERVICE_COLS.ID_USER) || '').trim() === target) {
      return true;
    }
  }
  return false;
}

function buildNewBpRow(membresiaRow, membresiaHeaders, bpHeaderRow, bpHeaders, idUser) {
  const row = new Array(bpHeaderRow.length).fill('');
  const whatsapp = parseWhatsApp(getCell_(membresiaRow, membresiaHeaders, MEMBRESIA_COLS.TEM_WHATSAPP));

  setCell_(row, bpHeaders, BP_SERVICE_COLS.ID_USER, idUser);
  setCell_(row, bpHeaders, BP_SERVICE_COLS.NOME, getCell_(membresiaRow, membresiaHeaders, MEMBRESIA_COLS.NOME));
  setCell_(row, bpHeaders, BP_SERVICE_COLS.TELEFONE, getCell_(membresiaRow, membresiaHeaders, MEMBRESIA_COLS.TELEFONE));
  setCell_(row, bpHeaders, BP_SERVICE_COLS.EMAIL, getCell_(membresiaRow, membresiaHeaders, MEMBRESIA_COLS.EMAIL));
  setCell_(row, bpHeaders, BP_SERVICE_COLS.CODIGO_POSTAL, getCell_(membresiaRow, membresiaHeaders, MEMBRESIA_COLS.CODIGO_POSTAL));
  setCell_(row, bpHeaders, BP_SERVICE_COLS.MORADA, getCell_(membresiaRow, membresiaHeaders, MEMBRESIA_COLS.MORADA));
  setCell_(row, bpHeaders, BP_SERVICE_COLS.FREGUESIA, getCell_(membresiaRow, membresiaHeaders, MEMBRESIA_COLS.FREGUESIA));
  setCell_(row, bpHeaders, BP_SERVICE_COLS.DATA_NASCIMENTO, formatDateForBpService_(getCell_(membresiaRow, membresiaHeaders, MEMBRESIA_COLS.DATA_NASCIMENTO)));
  setCell_(row, bpHeaders, BP_SERVICE_COLS.DISCIPULADO, getCell_(membresiaRow, membresiaHeaders, MEMBRESIA_COLS.DISCIPULADO));

  if (whatsapp !== null) {
    setCell_(row, bpHeaders, BP_SERVICE_COLS.WHATSAPP, whatsapp);
  }

  if (whatsapp === false) {
    setCell_(row, bpHeaders, BP_SERVICE_COLS.NUMBER_WHATSAPP, getCell_(membresiaRow, membresiaHeaders, MEMBRESIA_COLS.NUMBER_WHATSAPP));
  }

  return row;
}

function formatDateForBpService_(value) {
  const normalized = normalizeDate(value);
  if (!normalized) {
    return '';
  }
  const parts = normalized.split('-');
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

function applyMembresiaBpChanges_(sheetMembresia, sheetBpService, membresiaHeaders, flagUpdates, newRows) {
  if (newRows.length > 0) {
    const startRow = sheetBpService.getLastRow() + 1;
    sheetBpService.getRange(startRow, 1, newRows.length, newRows[0].length).setValues(newRows);
    SpreadsheetApp.flush();
    validateNewBpRowsPersisted_(sheetBpService, newRows);
  }

  if (flagUpdates.length > 0) {
    const flagCol = membresiaHeaders[MEMBRESIA_COLS.FLAG_BP_SERVICE] + 1;
    const ranges = flagUpdates.map(update => `${columnToLetter_(flagCol)}${update.row}`);
    sheetMembresia.getRangeList(ranges).setValue(true);
  }
}

function columnToLetter_(column) {
  let temp = column;
  let letter = '';
  while (temp > 0) {
    const mod = (temp - 1) % 26;
    letter = String.fromCharCode(65 + mod) + letter;
    temp = Math.floor((temp - mod) / 26);
  }
  return letter;
}

function validateNewBpRowsPersisted_(sheetBpService, newRows) {
  const values = sheetBpService.getDataRange().getValues();
  const headers = mapHeaders(values[0] || []);
  validateRequiredHeaders_(headers, [BP_SERVICE_COLS.ID_USER], 'BP SERVICE');

  const persistedIds = {};
  for (let i = 1; i < values.length; i++) {
    const id = String(getCell_(values[i], headers, BP_SERVICE_COLS.ID_USER) || '').trim();
    if (id) {
      persistedIds[id] = true;
    }
  }

  const missing = newRows
    .map(row => String(getCell_(row, headers, BP_SERVICE_COLS.ID_USER) || '').trim())
    .filter(id => id && !persistedIds[id]);

  if (missing.length > 0) {
    throw new Error(`Criação em BP SERVICE não validada para ID_USER: ${missing.join(', ')}`);
  }
}

function logDryRunDetails_(encontrados, criados, ambiguos, erros, flagUpdates, newRows) {
  logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX} ALTERAÇÕES PREVISTAS`);
  logLine_(`Flags Membresia.BP SERVICE -> TRUE: ${flagUpdates.map(item => item.row).join(', ') || '(nenhuma)'}`);
  logLine_(`Novas linhas BP SERVICE: ${newRows.length}`);

  logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX} ENCONTRADOS`);
  encontrados.forEach(item => logLine_(`Linha=${item.linha} Nome=${item.nome} ID_USER=${item.idUser} Metodo=${item.metodo}`));

  logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX} NOVOS COLABORADORES`);
  criados.forEach(item => logLine_(`Linha=${item.linha} Nome=${item.nome} ID_USER=${item.idUser}`));

  logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX} AMBIGUIDADES`);
  ambiguos.forEach(item => logLine_(`Linha=${item.linha} Nome=${item.nome} Motivo=${item.motivo} IDs=${item.ids.join(', ')}`));

  logLine_(`${MEMBRESIA_BP_CONFIG.LOG_PREFIX} ERROS`);
  erros.forEach(item => logLine_(`Linha=${item.linha} Nome=${item.nome} Erro=${item.erro}`));
}

function logLine_(message) {
  Logger.log(message);
}
