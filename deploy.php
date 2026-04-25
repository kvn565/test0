<?php
define('SECRET', 'METTEZ_VOTRE_CLE_ICI');
define('APP_DIR', '/home/gcbvghdlauy/app.facturation.bi');
define('VENV_PYTHON', '/home/gcbvghdlauy/virtualenv/app.facturation.bi/3.12/bin/python');
define('VENV_PIP',    '/home/gcbvghdlauy/virtualenv/app.facturation.bi/3.12/bin/pip');
define('LOG_FILE',    '/home/gcbvghdlauy/deploy.log');

function log_msg($msg) {
    file_put_contents(LOG_FILE, date('[Y-m-d H:i:s] ') . $msg . "\n", FILE_APPEND);
}

$payload = file_get_contents('php://input');
$sig = 'sha256=' . hash_hmac('sha256', $payload, SECRET);

if (!hash_equals($sig, $_SERVER['HTTP_X_HUB_SIGNATURE_256'] ?? '')) {
    http_response_code(403);
    log_msg('ERREUR: Signature invalide');
    die('Signature invalide');
}

$data = json_decode($payload, true);
if (($data['ref'] ?? '') !== 'refs/heads/main') {
    log_msg('Branche ignoree: ' . ($data['ref'] ?? 'inconnue'));
    echo 'Branche ignoree';
    exit;
}

log_msg('=== Deploiement demarre ===');

$python  = VENV_PYTHON;
$pip     = VENV_PIP;
$manage  = APP_DIR . '/manage.py';
$app_dir = APP_DIR;

$commands = [
    'git pull'          => "cd $app_dir && git pull origin main 2>&1",
    'pip install'       => "$pip install -r $app_dir/requirements.txt 2>&1",
    'migrate'           => "$python $manage migrate --noinput 2>&1",
    'collectstatic'     => "$python $manage collectstatic --noinput 2>&1",
    'restart passenger' => "mkdir -p $app_dir/tmp && touch $app_dir/tmp/restart.txt 2>&1",
];

$output = '';
foreach ($commands as $label => $cmd) {
    log_msg(">> $label");
    $result = shell_exec($cmd);
    log_msg($result ?? '(aucune sortie)');
    $output .= "<h3>$label</h3><pre>" . htmlspecialchars($result ?? '') . "</pre>";
}

log_msg('=== Deploiement termine ===');
echo $output;
?>
