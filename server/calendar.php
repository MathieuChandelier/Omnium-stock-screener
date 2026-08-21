<?php
// calendar.php — selections du Market Calendar Omnium (INSTRUCTIONS_CALENDAR.md)
// A deposer sur model.omnium-capital.com, a cote de dismiss.php. PHP >= 7.4.
// API :
//   GET  ?user=slug              -> {"selected":[...], "lastTriaged": "ISO"|null}
//   GET  ?user=slug&ics=1        -> flux text/calendar (abonnement Google "From URL")
//   POST ?user=slug&action=add     body {"event":{id,ticker,date,label,type,source,status}}
//   POST ?user=slug&action=remove  body {"id":"..."}
//   POST ?user=slug&action=triaged body {"generatedAt":"ISO du run trie","dismissedIds":["..."]}
//        (dismissedIds = evenements VUS et non acceptes : jamais re-proposes)
//   POST ?user=slug&action=reset   -> vide selections/refus (tests) ; le
//        calendrier Google abonne se videra au prochain rafraichissement du flux
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit; }

$dir = __DIR__ . '/calendar_store';
if (!is_dir($dir)) { mkdir($dir, 0775, true); }
$user = preg_replace('/[^a-z0-9]/', '', strtolower($_GET['user'] ?? ''));
if (!$user) { http_response_code(400); header('Content-Type: application/json'); echo '{"error":"user required"}'; exit; }
$f = "$dir/$user.json";

$load = function () use ($f) {
  if (!file_exists($f)) return ['selected' => [], 'dismissed' => [], 'lastTriaged' => null];
  $j = json_decode(file_get_contents($f), true);
  return is_array($j) ? $j + ['selected' => [], 'dismissed' => [], 'lastTriaged' => null] : ['selected' => [], 'dismissed' => [], 'lastTriaged' => null];
};
$save = function ($d) use ($f) { file_put_contents($f, json_encode($d, JSON_UNESCAPED_UNICODE), LOCK_EX); };

// ── SYNC GOOGLE CALENDAR DIRECTE (option B, 21/08/2026) ──────────────
// Ecrit les evenements acceptes DIRECTEMENT dans un agenda Google dedie
// via un compte de service (ajout/suppression instantanes - l'abonnement
// ICS restait tributaire du rafraichissement Google, 8-24h).
// Configuration (deux fichiers a cote de ce script, proteges par
// .htaccess - voir INSTRUCTIONS_CALENDAR.md) :
//   gcal_key.json    : cle JSON du compte de service (telechargee de la
//                      console Google Cloud, nom d'origine quelconque)
//   gcal_config.json : {"calendarId":"xxxx@group.calendar.google.com"}
//                      (l'agenda DEDIE, partage avec le compte de service
//                      en "Apporter des modifications aux evenements")
// Sans ces fichiers, toute la sync est SILENCIEUSEMENT sautee : le store
// et le flux ICS continuent de fonctionner a l'identique.
// Id d'evenement Google = md5(user + id omnium) : idempotent (un re-add
// ecrase via PATCH apres 409), suppression sans table de correspondance.
function gcal_config() {
  static $cfg = null;
  if ($cfg !== null) return $cfg;
  $cfg = false;
  $kf = __DIR__ . '/gcal_key.json'; $cf = __DIR__ . '/gcal_config.json';
  if (!file_exists($kf) || !file_exists($cf)) return $cfg;
  $key = json_decode(file_get_contents($kf), true);
  $conf = json_decode(file_get_contents($cf), true);
  if (!is_array($key) || empty($key['client_email']) || empty($key['private_key'])) return $cfg;
  if (!is_array($conf) || empty($conf['calendarId'])) return $cfg;
  $cfg = ['key' => $key, 'calendarId' => $conf['calendarId']];
  return $cfg;
}
function gcal_b64($s) { return rtrim(strtr(base64_encode($s), '+/', '-_'), '='); }
function gcal_token() {
  $cfg = gcal_config(); if (!$cfg) return null;
  $cacheF = __DIR__ . '/gcal_token_cache.json';
  if (file_exists($cacheF)) {
    $c = json_decode(file_get_contents($cacheF), true);
    if (is_array($c) && !empty($c['token']) && ($c['exp'] ?? 0) > time() + 60) return $c['token'];
  }
  $now = time();
  $jwt = gcal_b64(json_encode(['alg' => 'RS256', 'typ' => 'JWT']))
    . '.' . gcal_b64(json_encode([
        'iss' => $cfg['key']['client_email'],
        'scope' => 'https://www.googleapis.com/auth/calendar.events',
        'aud' => 'https://oauth2.googleapis.com/token',
        'iat' => $now, 'exp' => $now + 3600,
      ]));
  $sig = '';
  if (!openssl_sign($jwt, $sig, $cfg['key']['private_key'], 'sha256WithRSAEncryption')) return null;
  $jwt .= '.' . gcal_b64($sig);
  $ch = curl_init('https://oauth2.googleapis.com/token');
  curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 8,
    CURLOPT_POSTFIELDS => http_build_query(['grant_type' => 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion' => $jwt])]);
  $resp = curl_exec($ch); curl_close($ch);
  $j = json_decode($resp ?: '', true);
  if (empty($j['access_token'])) return null;
  file_put_contents($cacheF, json_encode(['token' => $j['access_token'], 'exp' => time() + (int)($j['expires_in'] ?? 3600) - 30]), LOCK_EX);
  return $j['access_token'];
}
function gcal_call($method, $path, $body = null) {
  $cfg = gcal_config(); $tok = gcal_token();
  if (!$cfg || !$tok) return ['skipped', 0];
  $url = 'https://www.googleapis.com/calendar/v3/calendars/' . rawurlencode($cfg['calendarId']) . $path;
  $ch = curl_init($url);
  $hdr = ['Authorization: Bearer ' . $tok];
  if ($body !== null) $hdr[] = 'Content-Type: application/json';
  curl_setopt_array($ch, [CURLOPT_CUSTOMREQUEST => $method, CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 8, CURLOPT_HTTPHEADER => $hdr]);
  if ($body !== null) curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body, JSON_UNESCAPED_UNICODE));
  $resp = curl_exec($ch);
  $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE); curl_close($ch);
  return [$resp, $code];
}
// Corps d'evenement Google : MEME semantique que la branche ICS (heure de
// la source si capturee, sinon 22:00 Europe/Paris pour les earnings et
// journee entiere pour le reste ; url en propriete source ET en tete de
// description).
function gcal_event_body($e) {
  $date = $e['date'] ?? '';
  if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) return null;
  $sum = ($e['ticker'] ?? '') . ' — ' . ($e['label'] ?? '');
  $desc = trim(($e['type'] ?? '') . ' · ' . ($e['status'] ?? '') . ' · ' . ($e['source'] ?? ''), ' ·');
  $url = trim($e['url'] ?? '');
  $body = ['summary' => $sum];
  if ($url && preg_match('#^https?://#i', $url)) { $desc = $url . ($desc !== '' ? "\n" . $desc : ''); $body['source'] = ['title' => 'Event page', 'url' => $url]; }
  if ($desc !== '') $body['description'] = $desc;
  $time = $e['time'] ?? '';
  if (!preg_match('/^\d{2}:\d{2}$/', $time) && ($e['type'] ?? '') === 'earnings') { $time = '22:00'; }
  if (preg_match('/^\d{2}:\d{2}$/', $time)) {
    $startTs = strtotime("$date $time:00");
    $body['start'] = ['dateTime' => date('Y-m-d\TH:i:s', $startTs), 'timeZone' => 'Europe/Paris'];
    $body['end']   = ['dateTime' => date('Y-m-d\TH:i:s', $startTs + 3600), 'timeZone' => 'Europe/Paris'];
  } else {
    $body['start'] = ['date' => $date];
    $body['end']   = ['date' => date('Y-m-d', strtotime($date . ' +1 day'))];
  }
  return $body;
}
function gcal_upsert($user, $e) {
  $body = gcal_event_body($e); if ($body === null) return 'skipped';
  $gid = md5($user . '|' . ($e['id'] ?? '')); $body['id'] = $gid;
  list($resp, $code) = gcal_call('POST', '/events', $body);
  if ($resp === 'skipped') return 'skipped';
  if ($code === 409) { unset($body['id']); list($resp, $code) = gcal_call('PATCH', '/events/' . $gid, $body); }
  return ($code >= 200 && $code < 300) ? 'ok' : 'error http ' . $code;
}
function gcal_remove($user, $omniumId) {
  $gid = md5($user . '|' . $omniumId);
  list($resp, $code) = gcal_call('DELETE', '/events/' . $gid);
  if ($resp === 'skipped') return 'skipped';
  return ($code === 204 || $code === 404 || $code === 410) ? 'ok' : 'error http ' . $code;
}

if (isset($_GET['ics'])) {
  $d = $load();
  header('Content-Type: text/calendar; charset=utf-8');
  header('Content-Disposition: inline; filename="omnium-market-calendar.ics"');
  $out = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Omnium//MarketCalendar//FR\r\nX-WR-CALNAME:Omnium Market Calendar\r\nCALSCALE:GREGORIAN\r\n";
  // VTIMEZONE Europe/Paris : requis pour les evenements HORODATES
  // (decision 20/08 : l heure vit dans le calendrier Google, pas dans le
  // dashboard - earnings sans heure connue = 22:00 Paris, la cloture US).
  $out .= "BEGIN:VTIMEZONE\r\nTZID:Europe/Paris\r\nBEGIN:DAYLIGHT\r\nTZOFFSETFROM:+0100\r\nTZOFFSETTO:+0200\r\nTZNAME:CEST\r\nDTSTART:19700329T020000\r\nRRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU\r\nEND:DAYLIGHT\r\nBEGIN:STANDARD\r\nTZOFFSETFROM:+0200\r\nTZOFFSETTO:+0100\r\nTZNAME:CET\r\nDTSTART:19701025T030000\r\nRRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU\r\nEND:STANDARD\r\nEND:VTIMEZONE\r\n";
  foreach ($d['selected'] as $e) {
    $date = $e['date'] ?? ''; $dt = str_replace('-', '', $date);
    if (strlen($dt) !== 8) continue;
    $uid = preg_replace('/[^A-Za-z0-9\-]/', '', $e['id'] ?? uniqid()) . '@omnium';
    $sum = addcslashes(($e['ticker'] ?? '') . ' — ' . ($e['label'] ?? ''), ",;\\");
    $desc = addcslashes(trim(($e['type'] ?? '') . ' · ' . ($e['status'] ?? '') . ' · ' . ($e['source'] ?? ''), ' ·'), ",;\\");
    // Lien precis de l evenement (21/08/2026) : quand la collecte a capture
    // une URL (page evenement IR, webcast, inscription), elle part dans le
    // calendrier Google - en propriete URL ET en tete de DESCRIPTION
    // (Google affiche la description de facon plus fiable que URL).
    $url = trim($e['url'] ?? '');
    $urlLine = '';
    if ($url && preg_match('#^https?://#i', $url)) {
      $urlEsc = addcslashes($url, ",;\\");
      $urlLine = "URL:$urlEsc\r\n";
      $desc = $urlEsc . ($desc !== '' ? '\n' . $desc : '');
    }
    // Heure de l evenement (HH:MM, Europe/Paris) : celle de la source si
    // capturee (champ "time" transmis tel quel par l app) ; a defaut,
    // 22:00 pour les EARNINGS (cloture de bourse US, le standard) ;
    // les autres types sans heure restent en journee entiere.
    $time = $e['time'] ?? '';
    if (!preg_match('/^\d{2}:\d{2}$/', $time) && ($e['type'] ?? '') === 'earnings') { $time = '22:00'; }
    if (preg_match('/^\d{2}:\d{2}$/', $time)) {
      $hm = str_replace(':', '', $time);
      $startTs = strtotime("$date $time:00");
      $endHm = date('His', $startTs + 3600);
      $endDt = date('Ymd', $startTs + 3600);
      $out .= "BEGIN:VEVENT\r\nUID:$uid\r\nDTSTAMP:" . gmdate('Ymd\THis\Z') . "\r\nDTSTART;TZID=Europe/Paris:{$dt}T{$hm}00\r\nDTEND;TZID=Europe/Paris:{$endDt}T{$endHm}\r\nSUMMARY:$sum\r\nDESCRIPTION:$desc\r\n{$urlLine}END:VEVENT\r\n";
    } else {
      $end = date('Ymd', strtotime($date . ' +1 day'));
      $out .= "BEGIN:VEVENT\r\nUID:$uid\r\nDTSTAMP:" . gmdate('Ymd\THis\Z') . "\r\nDTSTART;VALUE=DATE:$dt\r\nDTEND;VALUE=DATE:$end\r\nSUMMARY:$sum\r\nDESCRIPTION:$desc\r\n{$urlLine}END:VEVENT\r\n";
    }
  }
  echo $out . "END:VCALENDAR\r\n"; exit;
}

header('Content-Type: application/json');
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
  $body = json_decode(file_get_contents('php://input'), true) ?: [];
  $action = $_GET['action'] ?? ($body['action'] ?? '');
  $d = $load();
  $gcal = null; // etat de la sync Google renvoye au client (debug console)
  if ($action === 'add' && isset($body['event']['id'])) {
    $d['selected'] = array_values(array_filter($d['selected'], fn($e) => ($e['id'] ?? '') !== $body['event']['id']));
    $d['selected'][] = $body['event'];
    $gcal = gcal_upsert($user, $body['event']);
  } elseif ($action === 'remove' && isset($body['id'])) {
    $d['selected'] = array_values(array_filter($d['selected'], fn($e) => ($e['id'] ?? '') !== $body['id']));
    $gcal = gcal_remove($user, $body['id']);
  } elseif ($action === 'reset') {
    foreach ($d['selected'] as $e) { if (!empty($e['id'])) gcal_remove($user, $e['id']); }
    $d = ['selected' => [], 'dismissed' => [], 'lastTriaged' => null];
    $gcal = 'ok';
  } elseif ($action === 'triaged') {
    $d['lastTriaged'] = $body['generatedAt'] ?? gmdate('c');
    if (isset($body['dismissedIds']) && is_array($body['dismissedIds'])) {
      $d['dismissed'] = array_values(array_unique(array_merge($d['dismissed'] ?? [], array_filter($body['dismissedIds'], 'is_string'))));
    }
  } else { http_response_code(400); echo '{"error":"bad action"}'; exit; }
  $save($d);
  echo json_encode($gcal === null ? ['ok' => true] : ['ok' => true, 'gcal' => $gcal]); exit;
}
echo json_encode($load(), JSON_UNESCAPED_UNICODE);
