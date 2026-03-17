/**
 * SISTEMA GERADOR DE PACOTES MODBUS RTU - ARQUIVO PRINCIPAL
 * - Botão A (GPIO5): PAUSA
 * - Botão B (GPIO6): RETOMA
 * - Botão RESET (GPIO7): REINICIA DO ZERO (sem travamento)
 * 
 * NOVO COMPORTAMENTO:
 * 1. Pacote de configuração gerado APENAS UMA VEZ no início
 * 2. Depois, apenas pacotes de dados (990 por segundo)
 * 3. Reset regenera pacote de configuração
 * 4. Tensões incluídas nos pacotes de dados (22 bytes)
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "pico/stdlib.h"
#include "hardware/gpio.h"
// REMOVIDO: #include "hardware/uart.h"  // Não é mais necessário
#include "display.h"
#include "pacote_configuracao.h"
#include "pacote_dados.h"

// ============================================================================

// REMOVIDO: #define UART_ID uart0
// REMOVIDO: #define BAUD_RATE 115200
// REMOVIDO: #define UART_TX_PIN 0
// REMOVIDO: #define UART_RX_PIN 1

// ============================================================================

// ÁREA DE ARMAZENAMENTO DE DADOS DO SISTEMA
float tensoes_canais[NUM_CANAIS];
uint32_t contador_pacotes = 0;

// ESTADO DO SISTEMA
bool sistema_pausado = false;
bool configuracao_enviada = false;

// CONFIGURAÇÃO DE VELOCIDADE DO SISTEMA
#define FREQUENCIA_HZ 1000

// ============================================================================

// FUNÇÕES AUXILIARES

bool botao_pressionado(uint pin) {
    static uint32_t ultimo_tempo[8] = {0};
    static bool estado_anterior[8] = {true};
    
    bool estado_atual = gpio_get(pin);
    uint32_t agora = to_us_since_boot(get_absolute_time());
    
    if (agora - ultimo_tempo[pin] < 20000) {
        return false;
    }
    
    if (estado_anterior[pin] && !estado_atual) {
        ultimo_tempo[pin] = agora;
        estado_anterior[pin] = estado_atual;
        return true;
    }
    
    estado_anterior[pin] = estado_atual;
    return false;
}

bool botao_a_pressionado() {
    return botao_pressionado(5);
}

bool botao_b_pressionado() {
    return botao_pressionado(6);
}

bool botao_reset_pressionado() {
    static uint32_t ultimo_tempo_reset = 0;
    static bool estado_anterior_reset = true;
    
    bool estado_atual = gpio_get(7);
    uint32_t agora = to_ms_since_boot(get_absolute_time());
    
    if (agora - ultimo_tempo_reset < 10) {
        return false;
    }
    
    if (estado_anterior_reset && !estado_atual) {
        sleep_ms(5);
        if (!gpio_get(7)) {
            ultimo_tempo_reset = agora;
            estado_anterior_reset = estado_atual;
            printf("[RESET] Botão pressionado - verificando...\n");
            return true;
        }
    }
    
    estado_anterior_reset = estado_atual;
    return false;
}

// ============================================================================

// FUNÇÃO PARA ENVIAR PACOTE DE CONFIGURAÇÃO INICIAL

void enviar_configuracao_inicial(uint32_t *contador_pacotes) {
    printf("\n=== ENVIANDO PACOTE DE CONFIGURAÇÃO INICIAL ===\n");
    
    // Exemplo simplificado de pacote de configuração (24 bytes com CRC)
    uint8_t pacote_config[24];
    pacote_config[0] = MODBUS_HEADER_CONFIG;  // 0xAA
    pacote_config[1] = MODBUS_EMPTY_BYTE;     // 0x00
    for(int i = 0; i < 20; i++) {
        pacote_config[2 + i] = i % 256;
    }
    // CRC16 exemplo (0x1234)
    pacote_config[22] = 0x34;  // LSB
    pacote_config[23] = 0x12;  // MSB
    
    printf("  [CONFIG] Enviando %d bytes\n", 24);
    
    // ✅ ENVIAR VIA USB CDC
    fwrite(pacote_config, 1, 24, stdout);
    fflush(stdout);
    
    configuracao_enviada = true;
    
    clear_display();
    display_text_no_clear("CONFIG OK", 0, 0, 1);
    char buffer[24];
    snprintf(buffer, sizeof(buffer), "PKT: %lu", *contador_pacotes);
    display_text_no_clear(buffer, 0, 16, 1);
    show_display();
    
    sleep_ms(500);
    clear_display();
}

// ============================================================================

// FUNÇÃO PARA REINICIAR COMPLETAMENTE O SISTEMA

void reiniciar_sistema() {
    printf("\n=== REINICIANDO SISTEMA (BOTÃO RESET) ===\n");
    
    contador_pacotes = 0;
    configuracao_enviada = false;
    sistema_pausado = false;
    
    clear_display();
    display_text_no_clear("RESET", 0, 0, 2);
    display_text_no_clear("REINICIANDO", 0, 32, 1);
    show_display();
    
    sleep_ms(200);
    enviar_configuracao_inicial(&contador_pacotes);
    
    printf("\n=== SISTEMA REINICIADO - PRONTO PARA DADOS ===\n");
    
    clear_display();
    display_text_no_clear("ATIVO", 0, 0, 1);
    char temp[16];
    snprintf(temp, sizeof(temp), "PKT: %lu", contador_pacotes);
    display_text_no_clear(temp, 0, 16, 1);
    show_display();
}

// ============================================================================

// FUNÇÃO PRINCIPAL 

int main() {
    stdio_init_all();  // Inicializa USB CDC automaticamente
    sleep_ms(2500);

    printf("=== SISTEMA GERADOR DE PACOTES MODBUS 1kHz ===\n");
    printf("PACOTE CONFIG: Cabeçalho 0xAA, 24 bytes\n");
    printf("PACOTE DADOS:  Cabeçalho 0x55, %d bytes (com tensões)\n", TAMANHO_PACOTE_DADOS);
    printf("Botão A (GPIO5): PAUSA   |   Botão B (GPIO6): RETOMA   |   Botão RESET (GPIO7): REINICIA\n");
    printf("Velocidade: %d mensagens por segundo\n\n", FREQUENCIA_HZ);

    // 🚫 REMOVIDO: Inicialização de UART hardware
    // A USB CDC já está ativa com stdio_init_all()

    // CONFIGURAÇÃO DOS BOTÕES
    const uint pins_botoes[] = {5, 6, 7};
    for (int i = 0; i < 3; i++) {
        gpio_init(pins_botoes[i]);
        gpio_set_dir(pins_botoes[i], GPIO_IN);
        gpio_pull_up(pins_botoes[i]);
    }

    // INICIALIZAÇÃO DO DISPLAY
    display_init();
    display_text("INICIANDO...", 0, 0, 1);
    show_display();
    sleep_ms(1000);

    // FASE 2: ENVIO DO PACOTE DE CONFIGURAÇÃO (UMA ÚNICA VEZ)
    enviar_configuracao_inicial(&contador_pacotes);

    printf("\n=== INICIANDO TRANSMISSÃO DE DADOS A 1kHz ===\n");
    printf("Configuração enviada. Agora apenas pacotes de dados.\n");

    // FEEDBACK NO DISPLAY
    clear_display();
    display_text_no_clear("ATIVO", 0, 0, 1);
    show_display();

    // FASE 3: LOOP PRINCIPAL
    absolute_time_t next_time = get_absolute_time();
    uint32_t ultima_verificacao_reset = 0;

    while (1) {
        uint32_t agora_ms = to_ms_since_boot(get_absolute_time());
        
        // VERIFICAÇÃO DO BOTÃO RESET
        if (agora_ms - ultima_verificacao_reset >= 10) {
            if (botao_reset_pressionado()) {
                reiniciar_sistema();
                next_time = get_absolute_time();
            }
            ultima_verificacao_reset = agora_ms;
        }

        // CONTROLE POR BOTÕES
        if (botao_a_pressionado() && !sistema_pausado) {
            sistema_pausado = true;
            printf("\n=== SISTEMA PAUSADO (Botão A) ===\n");
            clear_display();
            display_text_no_clear("SISTEMA", 0, 0, 1);
            display_text_no_clear("PAUSADO", 0, 24, 1);
            show_display();
        }

        if (botao_b_pressionado() && sistema_pausado) {
            sistema_pausado = false;
            printf("\n=== SISTEMA RETOMADO (Botão B) ===\n");
            clear_display();
            display_text_no_clear("ATIVO", 0, 0, 1);
            show_display();
            next_time = get_absolute_time();
        }

        // MODO PAUSADO
        if (sistema_pausado) {
            static uint32_t ultima_atualizacao = 0;
            if (agora_ms - ultima_atualizacao > 500) {
                clear_display();
                display_text_no_clear("PAUSADO", 0, 0, 1);
                char temp[20];
                snprintf(temp, sizeof(temp), "PKT: %lu", contador_pacotes);
                display_text_no_clear(temp, 0, 16, 1);
                snprintf(temp, sizeof(temp), "CFG: %s", 
                         configuracao_enviada ? "OK" : "PEND");
                display_text_no_clear(temp, 0, 32, 1);
                show_display();
                ultima_atualizacao = agora_ms;
            }
            sleep_ms(10);
            continue;
        }

        // VERIFICA SE CONFIGURAÇÃO FOI ENVIADA
        if (!configuracao_enviada) {
            printf("ERRO: Configuração não enviada! Enviando agora...\n");
            enviar_configuracao_inicial(&contador_pacotes);
            continue;
        }

        // MODO ATIVO: PACOTES DE DADOS (1 kHz)
        contador_pacotes++;
        next_time = delayed_by_us(next_time, 1000);
        sleep_until(next_time);

        // ✅ CORRIGIDO: chamada sem parâmetro UART
        gerar_pacote_dados(tensoes_canais, &contador_pacotes);

        // Feedback periódico
        if (contador_pacotes % FREQUENCIA_HZ == 0) {
            uint32_t segundos = contador_pacotes / FREQUENCIA_HZ;
            printf("--- %lu pacotes de DADOS (%lu s) ---\n", 
                   contador_pacotes, segundos);
            
            clear_display();
            display_text_no_clear("DADOS ATIVO", 0, 0, 1);
            char buffer[24];
            snprintf(buffer, sizeof(buffer), "PKT: %lu", contador_pacotes);
            display_text_no_clear(buffer, 0, 16, 1);
            snprintf(buffer, sizeof(buffer), "T: %lu s", segundos);
            display_text_no_clear(buffer, 0, 32, 1);
            show_display();
        }

        if (contador_pacotes >= 2000000000) {
            contador_pacotes = 0;
            printf("\n=== CONTADOR REINICIADO ===\n");
        }
    }

    return 0;
}