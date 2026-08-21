<?php
// news.php — etat "vu" des notifications NEWS du dashboard Omnium
// A deposer sur model.omnium-capital.com, a cote de calendar.php. PHP >= 7.4.
// API :
//   GET  ?user=slug              -> {"seen":["TICKER-YYYYMMDD-slug", ...]}
//   POST ?user=slug&action=seen  body {"ids":["TICKER-YYYYMMDD-slug", ...]}
//        (marque ces items VUS - fusion idempotente)
//   POST ?user=slug&action=reset -> vide l'etat (tests)
// Hygiene : les ids embarquent leur date (TICKER-YYYYMMDD-slug) - tout id
// vieux de plus de 60 jours est purge au chargement, le store ne peut pas
// enfler sans fin (le flux data/newsFeed.json est fenetre sur 7 jours).
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit; }

$dir = __DIR__ . '/news_store';
if (!is_dir($dir)) { mkdir($dir, 0775, true); }
$user = preg_replace('/[^a-z0-9]/', '', strtolower($_GET['user'] ?? ''));
if (!$user) { http_response_code(400); header('Content-Type: application/json'); echo '{"error":"user required"}'; exit; }
$f = "$dir/$user.json";

$prune = function ($ids) {
  $lim = date('Ymd', time() - 60 * 86400);
  return array_values(array_filter($ids, function ($id) use ($lim) {
    if (!is_string($id)) return false;
    if (preg_match('/-(\d{8})-/', $id, $m)) return $m[1] >= $lim;
    return true; // id sans date lisible : conserve (defensif)
  }));
};
$load = function () use ($f, $prune) {
  if (!file_exists($f)) return ['seen' => []];
  $j = json_decode(file_get_contents($f), true);
  $seen = (is_array($j) && isset($j['seen']) && is_array($j['seen'])) ? $j['seen'] : [];
  return ['seen' => $prune($seen)];
};
$save = function ($d) use ($f) { file_put_contents($f, json_encode($d, JSON_UNESCAPED_UNICODE), LOCK_EX); };

header('Content-Type: application/json');
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
  $body = json_decode(file_get_contents('php://input'), true) ?: [];
  $action = $_GET['action'] ?? ($body['action'] ?? '');
  $d = $load();
  if ($action === 'seen' && isset($body['ids']) && is_array($body['ids'])) {
    $d['seen'] = array_values(array_unique(array_merge($d['seen'], array_filter($body['ids'], 'is_string'))));
  } elseif ($action === 'reset') {
    $d = ['seen' => []];
  } else { http_response_code(400); echo '{"error":"bad action"}'; exit; }
  $save($d); echo '{"ok":true}'; exit;
}
echo json_encode($load(), JSON_UNESCAPED_UNICODE);
