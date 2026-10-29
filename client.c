 #include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#include "common.h"

#define REGISTRY_IP "10.0.0.2"

int main(int argc, char *argv[])
{
    if (argc != 2) {
        printf("Usage: %s <HTTP|FTP>\n", argv[0]);
        return 1;
    }
    int sockfd;
    struct sockaddr_in registry_addr;

    char message[BUFFER_SIZE];
    snprintf(message, sizeof(message), "DISCOVER|%s", argv[1]);
    char buffer[BUFFER_SIZE];

    /*
     * Create UDP socket
     */
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);

    if (sockfd < 0)
    {
        perror("socket");
        exit(EXIT_FAILURE);
    }

    printf("[CLIENT] UDP socket created.\n");

    /*
     * Configure registry address
     */
    memset(&registry_addr, 0, sizeof(registry_addr));

    registry_addr.sin_family = AF_INET;
    registry_addr.sin_port = htons(REGISTRY_PORT);

    /*
     * Convert IP address
     */
    if (inet_pton(AF_INET,
                  REGISTRY_IP,
                  &registry_addr.sin_addr) <= 0)
    {
        perror("inet_pton");
        close(sockfd);
        exit(EXIT_FAILURE);
    }

    /*
     * Send message to registry
     */
    sendto(
        sockfd,
        message,
        strlen(message),
        0,
        (struct sockaddr *)&registry_addr,
        sizeof(registry_addr)
    );

    printf("[CLIENT] Sent: %s\n", message);

    /*
     * Wait for registry response
     */
    socklen_t addr_len = sizeof(registry_addr);

    int bytes_received = recvfrom(
        sockfd,
        buffer,
        BUFFER_SIZE - 1,
        0,
        (struct sockaddr *)&registry_addr,
        &addr_len
    );

    if (bytes_received < 0)
    {
        perror("recvfrom");
        close(sockfd);
        exit(EXIT_FAILURE);
    }

    buffer[bytes_received] = '\0';

    printf("[CLIENT] Received: %s\n", buffer);

    close(sockfd);

    return 0;
}
