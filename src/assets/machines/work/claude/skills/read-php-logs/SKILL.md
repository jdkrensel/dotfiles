---
name: read-php-logs
description: Find and read the CareSense PHP application log (phplogfile.log) on a staging or production web server over SSH. Use this whenever you need to see what the CareSense website actually did at runtime — tracing an upload, a controller action, an intake submission, an API call, a helper's info()/warn()/error() output, a fatal error, or "why did the page say X" — and whenever the user says "check the PHP logs", "look at the app log", "what does the log say", "grep the logs on staging", or names a log line or filename they want found. Reach for this before hand-rolling `find / -name '*.log'` or guessing a path, because the path recorded in the tracked repo is NOT the path used on the servers and guessing wastes several round-trips on an empty grep.
profiles: clb
---

# Reading CareSense PHP logs

The CareSense website logs through log4php to a single file per host. Getting to it is
fast once you know two things: the real directory, and the fact that the log is huge
so you must filter server-side rather than pulling it back.

## The one thing that will trip you up

The tracked repo says the log lives in `/var/log/php`
(`application/config/server_profiles/_server_basics.php:67`), but every deployed host
overrides that in `application/config/local_settings.php`, which is **gitignored** and
therefore invisible from the repo:

```php
$_APPLICATION['LogsDir'] = '/usr/local/var/log/php';
```

So the real path is:

```
/usr/local/var/log/php/phplogfile.log
```

On FreeBSD prod, `/var/log/php` happens to be a symlink to that directory, so the
documented path works by accident. On Linux staging there is no symlink and
`/var/log/php` **does not exist** — grepping it returns "No such file or directory",
which reads like "the event never happened" when it actually means "wrong path." Always
start from `/usr/local/var/log/php`.

If a host ever disagrees, ask the config rather than searching the filesystem:

```bash
ssh <host> 'bash -lc "grep LogsDir /usr/local/www/caresense/application/config/local_settings.php"'
```

The webroot is `/usr/local/www/caresense` (not `/var/www/html`, which on staging holds
only a default nginx placeholder).

## Hosts

| Alias | Environment | OS | Notes |
|---|---|---|---|
| `www_staging` | staging.caresense.com | Linux | rotations gzipped |
| `www_prod` | production | FreeBSD | rotations left uncompressed |

Both run `fish` as the login shell, which does not parse `$'...'` or `$(...)` inside a
remote command. Wrap every remote command in `bash -lc "..."` and prefer wrapping the
whole thing in **single** quotes so your local shell doesn't mangle `$` first:

```bash
ssh www_staging 'bash -lc "grep foo /usr/local/var/log/php/phplogfile.log | tail -20"'
```

You may see a harmless `fnm_multishells ... No space left on device` warning on stderr.
It comes from the shell's node version manager, not from disk pressure, and it is safe
to ignore — pipe it out with `| grep -v fnm_multishells` to keep output readable.

## The fast path

Use the bundled helper, which encodes the path, the `bash -lc` wrapper, the noise
filter, and rotated-file handling. Your working directory is usually some other repo, so
invoke it by absolute path:

```bash
PHPLOG=~/.claude-bedrock/skills/read-php-logs/scripts/phplog.sh

$PHPLOG <staging|prod> [--all] <grep-pattern> [tail-count]
```

Examples:

```bash
$PHPLOG staging test.csv
$PHPLOG staging 'WEB_4dtsuq2v56gk96q6ho5doufkt0' 60
$PHPLOG prod 'uploadToS3' 40
$PHPLOG staging --all 'notifyImporter' 60    # include rotated/gzipped history
```

Output shape differs by mode, which matters when you want to widen to a line range:
without `--all` each hit is prefixed `<line-number>:`; with `--all` it's prefixed
`<filename>:` instead (no line numbers), because hits span several files.

Reach for a raw `ssh` call when you need something the script doesn't cover — a
timestamp range, `-A`/`-B` context, or a count.

## Reading effectively

The log is tens of megabytes per day and interleaves every concurrent request, so how
you filter matters more than what you read.

**Filter on the server, never locally.** Always `grep` over SSH and `tail`/`head` the
result. Pulling the file back or catting it will flood the context for no benefit.

**Pick a high-specificity anchor.** Best to worst: a session id (`WEB_<php-session-id>`,
which scopes to exactly one user's request chain), a filename, a distinctive log-message
substring, then a bare function name. Bare function names match every user's traffic.

**Then widen to the surrounding arc.** Once you have one line, re-grep on its session id
to get that request's full sequence, or use `grep -n` and read a line range. A single
line rarely answers the question; the ordering of lines usually does.

**Line format** is `%d{Y-m-d H:i:s} %-5p %m [%F:%L]` — timestamp, level, message, then
source file and line. The `[file:line]` suffix is the fastest way back into the code, so
quote it when you report a finding.

Root log level is `INFO`, so `info()`, `warn()` and `error()` calls all land here.

### Timestamps are not in the same zone on both hosts

The timestamp comes from PHP's configured timezone, which differs by environment even
though the OS clock is UTC on both:

| Host | PHP timezone | Log timestamps are |
|---|---|---|
| staging | `UTC` | UTC — same as `date -u` |
| **prod** | `America/New_York` | **Eastern, i.e. UTC−4 in summer** |

So a prod line reading `14:16:12` is `18:16:12` UTC. This matters whenever you correlate
against UTC-stamped evidence — `imports.sqs_message_log`, S3 timestamps, CloudWatch —
because uncorrected prod times look like they happened *before* the events that caused
them. Convert explicitly, and say which zone you're quoting. To confirm on any host:

```bash
ssh <host> 'bash -lc "php -r \"echo date_default_timezone_get();\"; date -u"'
```

### Triaging errors

`WARN`/`ERROR` lines are often the whole answer, so start there:

```bash
$PHPLOG prod --errors 60
```

That is a convenience for `grep -E 'WARN |ERROR '`. The trailing space is deliberate —
matching bare `WARN` also hits the words inside message bodies and inflates any count.
Expect these to be dominated by a few chronic, recurring patterns rather than one new
incident, so group by `[file:line]` before concluding today's deploy broke something.

## Rotation

Current log: `phplogfile.log`. Rotated: `phplogfile.log-YYYYMMDD`, gzipped on staging.

The date suffix is **when the rotation ran, not the day the content covers**:
`phplogfile.log-20260806` holds *August 5th's* entries. This silently searches the wrong
day, so for anything not from today, prefer `--all` and let the filename in the output
tell you which day you actually landed on. Use `zgrep` for `.gz` files — `--all` does.

## What this log can and can't tell you

It records what the *website* did, which is narrower than what the system did. A line
saying a message was posted to NSQ proves the website wrote to the queue — not that the
importer consumed it, and not that an import happened. Likewise an upload's
`upload succeeded` proves the S3 write, not that anything downstream accepted the file.
When the question is really "did the import happen," this log gives you the handoff point
and the timestamp; the answer lives on the importer side (`imports.sqs_message_log`).
Say which of the two you've actually established.

## A second log exists

`sqllogfile.log` (from `includes/log_config_sql.php`) is a separate query log in the
same directory, and it is **not** present on every host. Application-flow lines are in
`phplogfile.log`; don't waste a round-trip looking for them in the SQL log.

## When a grep comes back empty

Empty means "not found *there*" — distinguish the causes before concluding the event
never happened:

1. Wrong directory — confirm `LogsDir` as shown above.
2. Wrong day — check the rotation off-by-one.
3. Pattern too specific — a filename may be logged with different surrounding text;
   retry on a shorter, more distinctive fragment.
4. Genuinely absent — only now is it evidence the code path didn't execute.

Worth knowing: log4php's `LoggerAppenderFile` fails **silently** if it can't open the
file. "The code calls `info()`" and "the line is on disk" are different claims, so if a
line you're certain executed is missing, check the log file's ownership and permissions
(it should be writable by the web user — `www-data` on staging, `www` on prod) before
concluding anything about the application's behavior.
