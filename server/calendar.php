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
  if ($action === 'add' && isset($body['event']['id'])) {
    $d['selected'] = array_values(array_filter($d['selected'], fn($e) => ($e['id'] ?? '') !== $body['event']['id']));
    $d['selected'][] = $body['event'];
  } elseif ($action === 'remove' && isset($body['id'])) {
    $d['selected'] = array_values(array_filter($d['selected'], fn($e) => ($e['id'] ?? '') !== $body['id']));
  } elseif ($action === 'reset') {
    $d = ['selected' => [], 'dismissed' => [], 'lastTriaged' => null];
  } elseif ($action === 'triaged') {
    $d['lastTriaged'] = $body['generatedAt'] ?? gmdate('c');
    if (isset($body['dismissedIds']) && is_array($body['dismissedIds'])) {
      $d['dismissed'] = array_values(array_unique(array_merge($d['dismissed'] ?? [], array_filter($body['dismissedIds'], 'is_string'))));
    }
  } else { http_response_code(400); echo '{"error":"bad action"}'; exit; }
  $save($d); echo '{"ok":true}'; exit;
}
echo json_encode($load(), JSON_UNESCAPED_UNICODE);
