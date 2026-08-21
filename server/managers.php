<?php
// managers.php — retention manuelle des mouvements de gerants 13F du dashboard
// Omnium (INSTRUCTIONS_MANAGERS.md, run trimestriel -> data/managerMoves.json).
// A deposer sur model.omnium-capital.com, a cote de calendar.php / news.php.
// PHP >= 7.4.
//
// POURQUOI UN ENDPOINT : l'app est STATIQUE (GitHub Pages) et ne peut pas
// ecrire dans data/<TICKER>.json. La retention d'un mouvement est donc
// stockee ici (comme le tri du calendrier), et une session LLM l'applique
// ensuite dans le champ ownership des fiches, puis vide la file via
// action=applied. Meme forme de repli que news.php : si le fichier n'est
// pas deploye, l'app bascule silencieusement sur localStorage.
//
// API :
//   GET  ?user=slug                 -> {"retained":[{...mouvement}], "dismissed":["id", ...]}
//   POST ?user=slug&action=retain   body {"move":{"id":"...","ticker":"...", ...}}
//        (je retiens ce mouvement : il doit entrer dans l'ownership du titre)
//   POST ?user=slug&action=dismiss  body {"id":"..."}
//        (traite, sans suite : ne reapparait plus dans la carte NEWS)
//   POST ?user=slug&action=applied  body {"ids":["...", "..."]}
//        (la session LLM a ecrit ces mouvements dans les fiches : on les
//         retire de la file de retention - c'est la SEULE operation qui
//         retire un mouvement de "retained")
//   POST ?user=slug&action=reset    -> vide tout (tests)
//
// Hygiene : les ids embarquent leur trimestre (TICKER-YYYYQn-slug) - toute
// entree anterieure aux 5 derniers trimestres est purgee au chargement, le
// store ne peut pas enfler sans fin.
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit; }

$dir = __DIR__ . '/managers_store';
if (!is_dir($dir)) { mkdir($dir, 0775, true); }
$user = preg_replace('/[^a-z0-9]/', '', strtolower($_GET['user'] ?? ''));
if (!$user) { http_response_code(400); header('Content-Type: application/json'); echo '{"error":"user required"}'; exit; }
$f = "$dir/$user.json";

// Index de trimestre absolu (annee*4 + n-1) : permet de comparer 2025Q4 et
// 2026Q1 sans arithmetique de dates.
$qIndexNow = (function () {
  $y = (int) date('Y');
  $q = (int) ceil(((int) date('n')) / 3);
  return $y * 4 + ($q - 1);
})();
$qOfId = function ($id) {
  if (!is_string($id)) return null;
  if (preg_match('/-(\d{4})Q([1-4])-/', $id, $m)) return ((int) $m[1]) * 4 + ((int) $m[2] - 1);
  return null; // id sans trimestre lisible : conserve (defensif)
};
$fresh = function ($id) use ($qOfId, $qIndexNow) {
  $qi = $qOfId($id);
  return $qi === null ? true : $qi >= ($qIndexNow - 5);
};

$load = function () use ($f, $fresh) {
  $d = ['retained' => [], 'dismissed' => []];
  if (!file_exists($f)) return $d;
  $j = json_decode(file_get_contents($f), true);
  if (!is_array($j)) return $d;
  $ret = (isset($j['retained']) && is_array($j['retained'])) ? $j['retained'] : [];
  $dis = (isset($j['dismissed']) && is_array($j['dismissed'])) ? $j['dismissed'] : [];
  $d['retained'] = array_values(array_filter($ret, function ($m) use ($fresh) {
    return is_array($m) && !empty($m['id']) && is_string($m['id']) && $fresh($m['id']);
  }));
  $d['dismissed'] = array_values(array_filter($dis, function ($id) use ($fresh) {
    return is_string($id) && $fresh($id);
  }));
  return $d;
};
$save = function ($d) use ($f) { file_put_contents($f, json_encode($d, JSON_UNESCAPED_UNICODE), LOCK_EX); };

header('Content-Type: application/json');
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
  $body = json_decode(file_get_contents('php://input'), true) ?: [];
  $action = $_GET['action'] ?? ($body['action'] ?? '');
  $d = $load();

  if ($action === 'retain' && isset($body['move']) && is_array($body['move']) && !empty($body['move']['id'])) {
    $mv = $body['move'];
    $id = (string) $mv['id'];
    // Idempotent : un mouvement deja retenu est remplace, jamais duplique.
    $d['retained'] = array_values(array_filter($d['retained'], function ($m) use ($id) {
      return !isset($m['id']) || $m['id'] !== $id;
    }));
    $d['retained'][] = $mv;
    // Retenir un mouvement precedemment ecarte le sort de la liste des ecartes.
    $d['dismissed'] = array_values(array_filter($d['dismissed'], function ($x) use ($id) { return $x !== $id; }));

  } elseif ($action === 'dismiss' && isset($body['id']) && is_string($body['id'])) {
    $id = $body['id'];
    if (!in_array($id, $d['dismissed'], true)) $d['dismissed'][] = $id;
    $d['retained'] = array_values(array_filter($d['retained'], function ($m) use ($id) {
      return !isset($m['id']) || $m['id'] !== $id;
    }));

  } elseif ($action === 'applied' && isset($body['ids']) && is_array($body['ids'])) {
    $ids = array_values(array_filter($body['ids'], 'is_string'));
    // Applique = sorti de la file de retention ET definitivement traite :
    // le mouvement ne doit pas revenir dans la carte NEWS au rechargement.
    $d['retained'] = array_values(array_filter($d['retained'], function ($m) use ($ids) {
      return !isset($m['id']) || !in_array($m['id'], $ids, true);
    }));
    $d['dismissed'] = array_values(array_unique(array_merge($d['dismissed'], $ids)));

  } elseif ($action === 'reset') {
    $d = ['retained' => [], 'dismissed' => []];

  } else {
    http_response_code(400); echo '{"error":"bad action"}'; exit;
  }

  $save($d); echo '{"ok":true}'; exit;
}
echo json_encode($load(), JSON_UNESCAPED_UNICODE);
