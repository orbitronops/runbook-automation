"""Simulated environment for the demo.

No live cluster, no real kubectl, no AWS. Each read-only command pattern
maps to a canned output, so a runbook can be executed end to end on a
laptop. The simulator never runs a shell command — matching is by
substring on the command text only.
"""
from __future__ import annotations

# (pattern, output, exit_code)
_CANNED: list[tuple[str, str, int]] = [
    (
        "kubectl describe pod checkout-api",
        "Name:         checkout-api-7d9f8\n"
        "Namespace:    prod\n"
        "Status:       CrashLoopBackOff\n"
        "Containers:\n"
        "  checkout-api:\n"
        "    Last State:     Terminated\n"
        "      Reason:       OOMKilled\n"
        "      Exit Code:    137\n"
        "    Restart Count:  12\n"
        "Events:\n"
        "  Warning  OOMKilling  Memory cgroup out of memory",
        0,
    ),
    (
        "kubectl logs checkout-api",
        "2026-11-15T10:02:11Z INFO  starting checkout-api\n"
        "2026-11-15T10:02:40Z ERROR java.lang.OutOfMemoryError: Java heap space\n"
        "2026-11-15T10:02:40Z ERROR at com.acme.checkout.CartService.load(CartService.java:41)",
        0,
    ),
    (
        "kubectl top pod checkout-api",
        "NAME                CPU(cores)   MEMORY(bytes)\n"
        "checkout-api-7d9f8   245m         511Mi",
        0,
    ),
    (
        "kubectl get pod checkout-api",
        "NAME                READY   STATUS             RESTARTS   AGE\n"
        "checkout-api-7d9f8   0/1     CrashLoopBackOff   12         42m\n"
        "Limits: memory 512Mi, cpu 500m",
        0,
    ),
    (
        "kubectl get events",
        "LAST SEEN   TYPE      REASON       OBJECT\n"
        "10m         Warning   OOMKilling   pod/checkout-api-7d9f8\n"
        "10m         Warning   BackOff      pod/checkout-api-7d9f8",
        0,
    ),
    (
        "kubectl get nodes",
        "NAME            STATUS   ROLES           AGE   VERSION\n"
        "node-a          Ready    <none>          90d   v1.32.0\n"
        "node-b          Ready    <none>          90d   v1.32.0\n"
        "node-c          NotReady <none>          90d   v1.32.0",
        0,
    ),
    (
        "kubectl describe node node-c",
        "Name:               node-c\n"
        "Conditions:\n"
        "  Type             Status\n"
        "  MemoryPressure   True\n"
        "  DiskPressure     True\n"
        "  Ready            False\n"
        "Allocated resources:\n"
        "  memory           15360Mi / 15872Mi (96%)\n"
        "  ephemeral-storage  92% used",
        0,
    ),
    (
        "kubectl top node",
        "NAME      CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%\n"
        "node-a    812m         20%    6420Mi          40%\n"
        "node-b    903m         22%    7102Mi          44%\n"
        "node-c    3901m        97%    15201Mi         96%",
        0,
    ),
    (
        "kubectl get pods --field-selector spec.nodeName=node-c",
        "NAME                READY   STATUS    RESTARTS   AGE\n"
        "batch-worker-3      1/1     Running   0          12d\n"
        "cache-warmer-1      1/1     Running   0          12d",
        0,
    ),
    (
        "kubectl get secret tls-checkout-api",
        "NAME                 TYPE                DATA   AGE\n"
        "tls-checkout-api     kubernetes.io/tls   2      340d",
        0,
    ),
    (
        "openssl x509",
        "notAfter=Nov 22 12:00:00 2026 GMT\n"
        "Certificate expires in 7 days",
        0,
    ),
    (
        "kubectl get ingress checkout-api",
        "NAME           CLASS   HOSTS                  ADDRESS        PORTS     AGE\n"
        "checkout-api   nginx   checkout.example.com   203.0.113.10   80, 443   340d",
        0,
    ),
    (
        "kubectl describe certificate",
        "Name:         tls-checkout-api\n"
        "Ready:        True\n"
        "Not After:    Nov 22 12:00:00 2026 GMT\n"
        "Renewal Time: Nov 15 12:00:00 2026 GMT",
        0,
    ),
]


def simulate(command: str) -> tuple[str, int]:
    """Return (output, exit_code) for a read-only command.

    Unknown commands are not executed — they return a clearly marked
    simulated failure so the expected-output check fails honestly.
    """
    for pattern, output, exit_code in _CANNED:
        if pattern in command:
            return output, exit_code
    return (
        f"simulated: no canned output for this command: {command}\n"
        "Add a canned response in simulator.py if this step should pass.",
        2,
    )


def check_expected(output: str, exit_code: int, expected: str) -> bool:
    """Evaluate an expected-output check: ``contains: X`` or ``exit_code: N``."""
    if not expected:
        return exit_code == 0
    kind, _, value = expected.partition(":")
    kind = kind.strip()
    value = value.strip()
    if kind == "contains":
        return value in output
    if kind == "exit_code":
        try:
            return exit_code == int(value)
        except ValueError:
            return False
    return False
