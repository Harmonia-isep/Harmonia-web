# Security policy

## Harmonia has no authentication, and that is deliberate

Harmonia is a single-user, local-first tool. It has **no login, no user accounts,
and no authorization checks of any kind**. The server binds `127.0.0.1` by
default, and on loopback an auth layer would be security theatre: anything able
to reach the port is already running as you, on your machine.

**Please do not file a vulnerability report for the absence of authentication,
authorization, rate limiting, CSRF tokens, or session management.** These are
documented design decisions, not oversights. Reports of this kind will be closed
with a link to this section.

The same applies to the direct consequences of that design:

- Any client that can reach the port can list, upload, analyze and **delete**
  tracks and playlists.
- Playlist share tokens are short, unauthenticated, and guessable by design.
  They are a convenience for a local network, not a security boundary.
- The API is fully open at `/docs` when the server is running.

### If you expose it, that is your security boundary

If you run Harmonia anywhere other than loopback, put it behind a reverse proxy
that provides authentication, and treat the proxy as the boundary. Harmonia will
not defend itself. Binding it to `0.0.0.0` on an untrusted network gives everyone
on that network full control of your library.

## What is in scope

Genuine vulnerabilities in the code as it is designed to be used are in scope.
For example:

- Path traversal in the upload, artwork, audio or static-file serving paths that
  reads or writes outside the configured directories.
- SQL injection, or any query built by string concatenation rather than through
  the ORM.
- A crafted audio file that causes arbitrary code execution rather than a clean
  parse failure.
- Dependency vulnerabilities that are actually reachable from Harmonia's code
  paths. Note that development-only advisories affecting the Vite dev server are
  not reachable from a production build.
- Anything that lets a **local** unprivileged user escalate through Harmonia to
  data they could not otherwise read.

## What is out of scope

- Missing authentication and everything downstream of it (see above).
- Anything that requires the operator to have already exposed the service to a
  hostile network without a proxy.
- Denial of service through deliberately enormous or malformed audio files. The
  upload path caps files at 20 MB; beyond that, this is a local tool and the
  operator controls the input.
- Findings from automated scanners with no demonstrated impact on Harmonia.

## Reporting

Report suspected vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/Harmonia-isep/Harmonia-web/security/advisories/new)
rather than in a public issue.

Please include the version or commit, the platform, and a minimal reproduction.
A proof of concept is welcome; a working exploit is not required and should not
be published before a fix exists.

This is a small project maintained in spare time. There is no guaranteed
response window and no bounty. Reports will be acknowledged and handled in good
faith as time allows.

## Supported versions

Only the tip of the default branch is supported. The `academic` branch and the
`v0.1.0-academic` tag are a frozen historical artifact of the original ISEP
capstone submission; they receive **no fixes of any kind** and should not be run.
