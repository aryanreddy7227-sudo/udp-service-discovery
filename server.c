#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <signal.h>

#include "common.h"

#define REGISTRY_IP "10.0.0.2"

#define SERVICE_NAME "HTTP"
#define SERVICE_IP "10.0.0.3"
#define SERVICE_PORT 8080

int sockfd;
struct sockaddr_in registry_addr;

void handle_sigint(int sig)
{
    char message[] = "DEREGISTER|HTTP";

    sendto(
        sockfd,
        message,
        strlen(message),
        0,
        (struct sockaddr *)&registry_addr,
        sizeof(registry_addr)
    );

    printf("\n[SERVER] Sent: %s\n", message);
    printf("[SERVER] Shutting down...\n");

    close(sockfd);

    exit(0);
}

int main()
{
    signal(SIGINT, handle_sigint);



    char message[BUFFER_SIZE];
    char buffer[BUFFER_SIZE];

    // Create UDP socket
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);

    if (sockfd < 0)
    {
        perror("socket");
        return 1;
    }

    printf("[SERVER] UDP socket created.\n");

    // Configure registry address
    memset(&registry_addr, 0, sizeof(registry_addr));

    registry_addr.sin_family = AF_INET;
    registry_addr.sin_port = htons(REGISTRY_PORT);

    inet_pton(AF_INET, REGISTRY_IP, &registry_addr.sin_addr);

    // Create registration message
    snprintf(
        message,
        BUFFER_SIZE,
        "REGISTER|%s|%s|%d",
        SERVICE_NAME,
        SERVICE_IP,
        SERVICE_PORT
    );

    // Send registration message
    sendto(
        sockfd,
        message,
        strlen(message),
        0,
        (struct sockaddr *)&registry_addr,
        sizeof(registry_addr)
    );

    printf("[SERVER] Sent: %s\n", message);

    // Wait for registry response
    socklen_t addr_len = sizeof(registry_addr);

    int n = recvfrom(
        sockfd,
        buffer,
        BUFFER_SIZE - 1,
        0,
        (struct sockaddr *)&registry_addr,
        &addr_len
    );

    if (n > 0)
    {
        buffer[n] = '\0';

        printf("[SERVER] Received: %s\n", buffer);
    }
    /* Send a heartbeat */
char heartbeat[BUFFER_SIZE];

snprintf(
    heartbeat,
    BUFFER_SIZE,
    "HEARTBEAT|%s|%s",
    SERVICE_NAME,
    SERVICE_IP
);

sendto(
    sockfd,
    heartbeat,
    strlen(heartbeat),
    0,
    (struct sockaddr *)&registry_addr,
    sizeof(registry_addr)
);

printf("[SERVER] Sent: %s\n", heartbeat);

/* Keep sending heartbeats */
while (1)
{
    sleep(5);

    sendto(
        sockfd,
        heartbeat,
        strlen(heartbeat),
        0,
        (struct sockaddr *)&registry_addr,
        sizeof(registry_addr)
    );

    printf("[SERVER] Sent: %s\n", heartbeat);
}

    close(sockfd);

    return 0;



}
