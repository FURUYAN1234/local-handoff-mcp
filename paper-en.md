# Workspace-Based Handoffs Between AI Development Agents

Local Handoff MCP v1.1.1 technical paper (English) | FURU

## Changes in version 1.1.1\n\nThe dashboard distinguishes browser sign-in from setup in older terminals. This release adds Strata over MCP in WSL, LM Studio port reporting and official setup links for missing clients.\n\n## Changes in version 1.1.0

Version 1.1.0 extends the fixed two-host transition to explicit recipients and keeps the original pair's implicit routing. A loopback dashboard reads project records and history. Client detection examines supported executables and MCP registrations; the user's chosen client handles its own sign-in. An opt-in scheduled command records bounded workspace observations without changing ownership or the written checkpoint. The examples and initial verification below describe baseline 1.0.0.

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

## Implementation supplement: state transitions, reproducibility, and failure boundaries

### Research questions and evidence

The study asks three questions. Do two clients pointing to the same directory read one ownership record? Can the service serialize competing updates to that record? Does the next action survive an explicit transfer, an interrupted session, and an installation update? The evidence comprises the release-tag implementation, automated tests and an isolated Windows profile exercise. User productivity, model compliance and multi-machine synchronization lie outside the measured sample.

### Resolving a workspace key

The input is an absolute path sent through MCP. The server maps Windows drive paths to WSL mounts and resolves the existing directory. Within an approved root, the closest Git repository becomes the unit of work. Without Git, the registered project directory is the unit. This design binds a record to files that both hosts can inspect across conversations. It rejects a tool request for a directory outside the registered set.

### Transitions and concurrent updates

The first checkpoint creates an active record and owner. An owner can update it through checkpoint. A competing checkpoint from the other host is rejected. The owner uses offer to enter the ready state. The designated recipient uses resume to become active. The recover action is available when the other host is active and the caller confirms that editing has stopped. The owner can close an active record with complete. A later request can use the same key for a new checkpoint.

Both the ownership check and the write occur within a SQLite BEGIN IMMEDIATE transaction. In an automated test, two competing first checkpoints produced one editing owner. The transaction guards updates to the handoff record. File editing and job execution take place elsewhere. At transfer time the receiving agent checks processes, artifacts and job status. The previous_stopped flag expresses the caller’s observation rather than a probe performed by the service.

### What Git can establish

The service returns branch, HEAD, counts for changed, untracked and conflicted entries, and a digest of the Git status listing. Editing a file already listed as modified may leave that digest unchanged. The digest covers status metadata. Confirm the content of the actual diff and output when resuming. If Git fails or times out, the service reports the unavailable status and returns the handoff record that it can read.

### Experimental conditions and reproduction

The tests ran on Windows with WSL 2 Ubuntu and system Python 3.12. Fetch the release tag and run /usr/bin/python3 -B -m unittest -v. Nine tests cover STDIO MCP discovery and a call, workspace isolation, transfer, contention, recovery, rejection of credential-like input, bounded Git metadata and installer conflict and upgrade behavior.

A separate run extracted the distribution ZIP and invoked Windows Install.bat with an isolated profile. The Codex registration wrote a sample checkpoint. The batch from a synthetic 1.0.1 package upgraded the installation. The Antigravity registration read the same owner and next action, and running the old batch was rejected. The 1.0.1 fixture was a test input. A clean checkout of the 1.0.0 tag also produced a byte-identical distribution ZIP.

### Operational boundaries

The system is intended for one operating-system user on one computer. Each host retains its own sign-in, quota, permissions and extensions. Portable procedures can live with the project, while host-specific connectors and execution settings require individual setup. Treat SQLite and settings as local project data. Keep secrets and complete transcripts out of checkpoints. Use the current request to decide whether a successor may deploy, publish, or start a billable job.
