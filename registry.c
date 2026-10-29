#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <time.h>
#include <errno.h>


#include "common.h"

#define MAX_SERVICES 100
#define HEARTBEAT_TIMEOUT 10

typedef struct
{
    char name[64];
    char ip[INET_ADDRSTRLEN];
    int port;
    int active;
    time_t last_seen;
} Service;

Service services[MAX_SERVICES];

int service_count = 0;

void print_services();

void check_heartbeats()
{
    time_t now = time(NULL);

    for (int i = 0; i < service_count; i++)
    {
        if (services[i].active &&
            difftime(now, services[i].last_seen) > HEARTBEAT_TIMEOUT)
        {
            services[i].active = 0;

            printf("[REGISTRY] Service timeout detected: %s\n",
                   services[i].name);

            print_services();
        }
    }
}

void print_services()
{
    printf("\n========== SERVICE TABLE ==========\n");

    if (service_count == 0)
    {
        printf("No services registered.\n");
    }

    for (int i = 0; i < service_count; i++)
    {
        if (services[i].active)
        {
            printf("%d. %s -> %s:%d\n",
                   i + 1,
                   services[i].name,
                   services[i].ip,
                   services[i].port);
        }
    }

    printf("===================================\n\n");
}

int main()
{
    int sockfd;

    struct sockaddr_in server_addr;
    struct sockaddr_in client_addr;

    char buffer[BUFFER_SIZE];

    socklen_t client_len = sizeof(client_addr);

    /*
     * Create UDP socket
     */
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);

    if (sockfd < 0)
    {
        perror("socket");
        exit(EXIT_FAILURE);
    }
    struct timeval tv;

    tv.tv_sec = 1;
    tv.tv_usec = 0;

    setsockopt(
    sockfd,
    SOL_SOCKET,
    SO_RCVTIMEO,
    &tv,
    sizeof(tv)
);

    printf("[REGISTRY] UDP socket created.\n");

    /*
     * Clear address structures
     */
    memset(&server_addr, 0, sizeof(server_addr));
    memset(&client_addr, 0, sizeof(client_addr));

    /*
     * Configure registry address
     */
    server_addr.sin_family = AF_INET;

    /*
     * Accept packets on any local IP address
     */
    server_addr.sin_addr.s_addr = INADDR_ANY;

    /*
     * Convert port to network byte order
     */
    server_addr.sin_port = htons(REGISTRY_PORT);

    /*
     * Bind socket to port 5000
     */
    if (bind(sockfd,
             (struct sockaddr *)&server_addr,
             sizeof(server_addr)) < 0)
    {
        perror("bind");
        close(sockfd);
        exit(EXIT_FAILURE);
    }

    printf("[REGISTRY] Listening on UDP port %d...\n",
           REGISTRY_PORT);

    /*
     * Continuously receive messages
     */
    while (1)
    {
        check_heartbeats();

        memset(buffer, 0, BUFFER_SIZE);

        int bytes_received = recvfrom(
            sockfd,
            buffer,
            BUFFER_SIZE - 1,
            0,
            (struct sockaddr *)&client_addr,
            &client_len
        );

        if (bytes_received < 0)
        {
            if (errno == EAGAIN || errno == EWOULDBLOCK)
            {
                continue;
            }

            perror("recvfrom");
            continue;
        }

        buffer[bytes_received] = '\0';

        printf("[REGISTRY] Received: %s\n", buffer);

        if (strncmp(buffer, "REGISTER|", 9) == 0)
{
    char service_name[64];
    char service_ip[INET_ADDRSTRLEN];
    int service_port;

    if (sscanf(buffer,
               "REGISTER|%63[^|]|%15[^|]|%d",
               service_name,
               service_ip,
               &service_port) == 3)
    {
        if (service_count < MAX_SERVICES)
        {
            strcpy(services[service_count].name, service_name);
            strcpy(services[service_count].ip, service_ip);
            services[service_count].port = service_port;
            services[service_count].active = 1;
            services[service_count].last_seen = time(NULL);

            service_count++;

            printf("[REGISTRY] Service registered successfully.\n");

            print_services();

            char response[] = "REGISTRY_ACK";

sendto(
    sockfd,
    response,
    strlen(response),
    0,
    (struct sockaddr *)&client_addr,
    client_len
);

printf("[REGISTRY] ACK sent.\n");
        }
        else
        {
            printf("[REGISTRY] Service table is full.\n");
        }
    }
    else
    {
        printf("[REGISTRY] Invalid REGISTER message.\n");
    }
}
if (strncmp(buffer, "DISCOVER|", 9) == 0)
{
    char requested_service[64];

    if (sscanf(buffer,
               "DISCOVER|%63s",
               requested_service) == 1)
    {
        int found = 0;

        for (int i = 0; i < service_count; i++)
        {
            if (services[i].active &&
                strcmp(services[i].name, requested_service) == 0)
            {
                char response[BUFFER_SIZE];

                snprintf(response,
                         BUFFER_SIZE,
                         "SERVICE|%s|%s|%d",
                         services[i].name,
                         services[i].ip,
                         services[i].port);

                sendto(
                    sockfd,
                    response,
                    strlen(response),
                    0,
                    (struct sockaddr *)&client_addr,
                    client_len
                );

                printf("[REGISTRY] Service found: %s\n",
                       requested_service);

                found = 1;
                break;
            }
        }

        if (!found)
        {
            char response[] = "SERVICE_NOT_FOUND";

            sendto(
                sockfd,
                response,
                strlen(response),
                0,
                (struct sockaddr *)&client_addr,
                client_len
            );

            printf("[REGISTRY] Service not found: %s\n",
                   requested_service);
        }
    }
}
    if (strncmp(buffer, "DEREGISTER|", 11) == 0)
{
    char service_name[64];

    if (sscanf(buffer,
               "DEREGISTER|%63s",
               service_name) == 1)
    {
        int found = 0;

        for (int i = 0; i < service_count; i++)
        {
            if (services[i].active &&
                strcmp(services[i].name, service_name) == 0)
            {
                services[i].active = 0;

                printf("[REGISTRY] Service deregistered: %s\n",
                       service_name);

                print_services();

                found = 1;
                break;
            }
        }

        if (!found)
        {
            printf("[REGISTRY] Service not found for deregistration: %s\n",
                   service_name);
        }
    }
}
if (strncmp(buffer, "HEARTBEAT|", 10) == 0)
{
    char service_name[64];

    if (sscanf(buffer,
               "HEARTBEAT|%63[^|]|%*s",
               service_name) == 1)
    {
        int found = 0;

        for (int i = 0; i < service_count; i++)
        {
            if (services[i].active &&
                strcmp(services[i].name, service_name) == 0)
            {
                services[i].last_seen = time(NULL);

                printf("[REGISTRY] Heartbeat received from: %s\n",
                       service_name);

                found = 1;
                break;
            }
        }

        if (!found)
        {
            printf("[REGISTRY] Heartbeat from unknown service: %s\n",
                   service_name);
        }
    }
}
        /*
         * Send acknowledgement
         */

    }

    close(sockfd);

    return 0;
}
