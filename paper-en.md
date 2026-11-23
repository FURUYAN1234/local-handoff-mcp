# Workspace-Based Handoffs Between AI Development Agents

Local Handoff MCP v1.0.0 technical paper (English) | FURU

## Abstract

This paper considers alternating between Codex and Antigravity on one computer. It uses the workspace as the durable reference point, storing the goal, next action, checks, job identifiers and editing owner in a local record. MCP over standard input and output and SQLite transactions support planned handoffs and recovery after a stopped session through the same state model.

## Why the workspace is the identifier

A usage limit often leaves the next client with a short request. Files, uncommitted Git changes and external jobs may outlive the original conversation. The service normalizes absolute paths and accepts approved workspaces only. In Git workspaces, branch, commit, change counts and a status digest let the receiving client compare present and recorded state. The MCP response omits the content of Git diffs.

## Transitions and concurrency

A first checkpoint claims editing ownership. In a planned transfer the owner calls offer and the receiving client calls resume. Recovery requires evidence that the previous client stopped, along with a check on the status of its jobs. The mutating tools validate the request, read ownership and write the resulting record within a SQLite write transaction. A probe using Windows access to a SQLite file exposed across the WSL filesystem boundary failed to acquire the lock. Both clients therefore invoke Linux processes in WSL to access the same database.

## Data and authority

The server communicates over local standard input and output. It queries registered workspaces and keeps bounded notes. Pattern checks reject typical credential formats. These checks are incomplete by design, so operators must control what they enter. A record describes earlier work and carries no new authority. Ownership guards MCP writes. External editors and commands remain subject to the users and clients operating them.

## Verification and reproduction

Run `/usr/bin/python3 -B -m unittest -v` at the release tag. Checks cover both host registrations over standard input and output, planned transfer, contention, recovery, rejection of out-of-scope paths and credential-like values, and safe handling of observations. Install and update tests start from Windows with an isolated profile, reopen the same database, and check downgrade rejection. The tests establish the behavior of the system under these scenarios. They do not estimate model adherence to instructions or quantify work saved.

## Conclusion

A shared workspace and explicit ownership move continuity from a conversation into verifiable project files and a resumable record. The intended environment is a single computer where one client edits a project at a time.
