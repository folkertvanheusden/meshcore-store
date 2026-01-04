#include <AsyncTCP.h>
#include <atomic>
#include <condition_variable>
#include <esp_mac.h>
#include <ESPmDNS.h>
#include <WiFiManager.h>
#include <ESPAsyncWebServer.h>  // included by wifimanager as well(?!)
#include <mutex>
#include <RadioLib.h>
#include <SPI.h>

#include "config.h"


// SX1262 radio setup
// NSS pin:   5
// DIO1 pin:  2
// NRST pin:  3
// BUSY pin:  4
#if defined(XIAO_HEADERS)
SX1262 radio = new Module(5, 2, 3, 4);

#elif defined(XIAO_CONNECTOR)
SX1262 radio = new Module(41, 39, 42, 40);

#elif defined(HELTEC_V3)
SX1262 radio = new Module(8, 14, 12, 13);

#elif defined(LILYGO_T3)
SX1276 radio = new Module(18, 26, 23);
#undef POWER
#define POWER        20

#elif defined(T_BEAM_1_2)
SX1276 radio = new Module(18, 26, 23);
#undef POWER
#define POWER        20

#elif defined(T_BEAM_SUPREME)
SPIClass    spi(HSPI);
SPISettings spi_settings(400000, MSBFIRST, SPI_MODE0);
SX1262      radio = new Module(10, 1, 5, 4, spi, spi_settings);

#else
#error please configure the ESP32 to SX1262 pins in mcb.ino
#endif

#define MAX_LORA_MSG_SIZE RADIOLIB_SX126X_MAX_PACKET_LENGTH

struct mc_message {
  uint8_t  buffer[MAX_LORA_MSG_SIZE];
  unsigned n;
};

#define MAX_QUEUE_ENTRIES 10
std::mutex websocket_receive_lock;
std::array<mc_message, MAX_QUEUE_ENTRIES> websocket_receive_entries;
int n_websocket_receive_entries = 0;

std::mutex websocket_transmit_lock;
std::array<mc_message, MAX_QUEUE_ENTRIES> websocket_transmit_entries;
int n_websocket_transmit_entries = 0;
std::condition_variable websocket_transmit_cv;

uint8_t rf_buffer[MAX_LORA_MSG_SIZE];

char    sys_id[19] { 0 };

#define HTTP_PORT 80
AsyncWebServer              *http_server = nullptr;
AsyncWebSocketMessageHandler wsHandler;
AsyncWebSocket               ws("/ws", wsHandler.eventHandler());
TaskHandle_t                 ws_handle;

void failed_reboot(const char *const txt) {
  Serial.println(txt);
  ESP.restart();
}

std::atomic_bool rf_received { false };

void ICACHE_RAM_ATTR set_rf_recv_flag() {
  rf_received = true;
}

void start_rf_receive() {
  auto state = radio.startReceive();
  if (state != RADIOLIB_ERR_NONE)
    failed_reboot("radio recv failed");
}

void set_builtin_led(const byte state) {
#if defined(LED_BUILTIN)
  digitalWrite(LED_BUILTIN, state);
#endif
}

void setup_http_server() {
  http_server = new AsyncWebServer(HTTP_PORT);

  http_server->on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    AsyncWebServerResponse *response = request->beginResponse(200, "text/text", "MeshCore websockets: " SELBOARD " / " AUTO_VERSION " / " __DATE__ " " __TIME__);
    request->send(response);
  });

  http_server->on("/status", HTTP_GET, [](AsyncWebServerRequest *request) {
    String response_text = "{ \"uptime\": " + String(millis()) + " }";
    AsyncWebServerResponse *response = request->beginResponse(200, "application/json", response_text);
    request->send(response);
  });

  http_server->on("/version", HTTP_GET, [](AsyncWebServerRequest *request) {
    String response_text = "{ \"board\": \"" + String(SELBOARD) + "\", \"GIT-hash\": \"" + String(AUTO_VERSION) + "\", \"build-on\": \"" + String(__DATE__ " " __TIME__) +  "\" }";
    AsyncWebServerResponse *response = request->beginResponse(200, "application/json", response_text);
    request->send(response);
  });

  wsHandler.onConnect([](AsyncWebSocket *server, AsyncWebSocketClient *client) {
      Serial.printf("Client %" PRIu32 " connected\r\n", client->id());
      });

  wsHandler.onDisconnect([](AsyncWebSocket *server, uint32_t clientId) {
    Serial.printf("Client %" PRIu32 " disconnected\r\n", clientId);
  });

  wsHandler.onError([](AsyncWebSocket *server, AsyncWebSocketClient *client, uint16_t errorCode, const char *reason, size_t len) {
    Serial.printf("Client %" PRIu32 " error: %" PRIu16 ": %s\r\n", client->id(), errorCode, reason);
  });

  wsHandler.onMessage([](AsyncWebSocket *server, AsyncWebSocketClient *client, const uint8_t *data, size_t len) {
    std::unique_lock<std::mutex> lck(websocket_receive_lock);
    if (n_websocket_receive_entries < MAX_QUEUE_ENTRIES) {
      memcpy(websocket_receive_entries[n_websocket_receive_entries].buffer, data, len);
      websocket_receive_entries[n_websocket_receive_entries].n = len;
      n_websocket_receive_entries++;
    }
  });

  wsHandler.onFragment([](AsyncWebSocket *server, AsyncWebSocketClient *client, const AwsFrameInfo *frameInfo, const uint8_t *data, size_t len) {
    Serial.printf("Client %" PRIu32 " fragment %" PRIu32 ": %s\n", client->id(), frameInfo->num, (const char *)data);
  });

  http_server->addHandler(&ws);

  http_server->begin();

  if (!MDNS.begin(sys_id))
    Serial.println(F("Failed initializing MDNS"));
  MDNS.setInstanceName(sys_id);
  MDNS.addService("http", "tcp", 80);
}

void ws_thread(void *) {
  uint32_t last_clean = 0;

  for(;;) {
    uint32_t now = millis();
    if (now - last_clean >= 500) {
      ws.cleanupClients();
      last_clean = now;
    }

    std::unique_lock<std::mutex> lck(websocket_transmit_lock);
    websocket_transmit_cv.wait_for(lck, std::chrono::milliseconds(50));
    for(int i=0; i<n_websocket_transmit_entries; i++)
        ws.binaryAll(websocket_transmit_entries[i].buffer, websocket_transmit_entries[i].n);
    int send_any = n_websocket_transmit_entries;
    n_websocket_transmit_entries = 0;
    lck.unlock();

    if (send_any)
      Serial.printf("Transmitted %d messages to websocket(s)\r\n", send_any);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println(F("Selected board: " SELBOARD));
  Serial.println(F("Git hash      : " AUTO_VERSION));
  Serial.println(F("Built on      : " __DATE__ " " __TIME__));

#if defined(LED_BUILTIN)
  pinMode(LED_BUILTIN, OUTPUT);
#endif

  Serial.print(F("[SX12xx] Initializing... "));
#if defined(T_BEAM_SUPREME)
  spi.begin(12, 13, 11, 10);
#endif
  auto state = radio.begin(CARRIER_FREQ, BANDWIDTH, SF, CR, SYNC_WORD, POWER, PREAMBLE);
  if (state == RADIOLIB_ERR_NONE)
    Serial.println(F("success!"));
  else
    failed_reboot("radio err");

  if (radio.setCRC(USE_CRC) == RADIOLIB_ERR_INVALID_CRC_CONFIGURATION)
    failed_reboot("radio setup failed");

  uint8_t mac[8];
  esp_efuse_mac_get_default(mac);
  Serial.print(F("MAC: "));
  for(int i=0; i<6; i++) {
    if (i)
      Serial.print(':');
    Serial.print(mac[i], HEX);
  }
  snprintf(sys_id, sizeof sys_id, "MCWS-%02x%02x%02x", mac[3], mac[4], mac[5]);
  Serial.print(F(", system ID: "));
  Serial.println(sys_id);

  WiFiManager wm;
  wm.setHostname(sys_id);
  wm.setConfigPortalTimeout(WIFI_PORTAL_TIMEOUT);
  wm.setConnectTimeout(WIFI_CONNECT_TIMEOUT);
  if (!wm.autoConnect(sys_id))
    failed_reboot("WiFi start fail");

  setup_http_server();

  xTaskCreatePinnedToCore(ws_thread, "WS", 16384, nullptr, 0, &ws_handle, 0);

  radio.setPacketReceivedAction(set_rf_recv_flag);
  start_rf_receive();

  Serial.println(F("Go!"));
}

void rf_transmit(const uint8_t *const pl, const size_t len) {
  set_builtin_led(HIGH);
  int state = radio.transmit(pl, len);
  if (state == RADIOLIB_ERR_NONE) {
  }
  else if (state == RADIOLIB_ERR_PACKET_TOO_LONG) {
    // the supplied packet was longer than 256 bytes
    Serial.println(F("rf packet too long"));
  }
  else if (state == RADIOLIB_ERR_TX_TIMEOUT) {
    // timeout occured while transmitting packet
    Serial.println(F("rf timeout"));
  }
  else {
    // some other error occurred
    Serial.print(F("rf transmission failed, code: "));
    Serial.println(state);
  }
  set_builtin_led(LOW);
}

void loop() {
  if (rf_received.exchange(false)) {
    int num_bytes = radio.getPacketLength();
    if (num_bytes == 0)
      Serial.println(F("RF ignoring empty msg"));
    else if (num_bytes > sizeof(rf_buffer)) {
      Serial.print(F("RF truncated: "));
      Serial.print(num_bytes - sizeof(rf_buffer));
      Serial.println(F(" too short"));
    }
    else {
      int state = radio.readData(rf_buffer, num_bytes);
      if (state == RADIOLIB_ERR_NONE) {
        // store in websocke transmit queue
        std::unique_lock<std::mutex> lck(websocket_transmit_lock);
        memcpy(websocket_transmit_entries[n_websocket_transmit_entries].buffer, rf_buffer, num_bytes);
        websocket_transmit_entries[n_websocket_transmit_entries].n = num_bytes;
        n_websocket_transmit_entries++;
        websocket_transmit_cv.notify_one();
      }
      else if (state == RADIOLIB_ERR_CRC_MISMATCH)
        Serial.println(F("CRC mismatch"));
      else {
        Serial.print(F("recv failed: "));
        Serial.println(state);
      }
    }
  }

  // transmit any message that came in via websockets
  std::unique_lock<std::mutex> lck(websocket_receive_lock);
  bool any_rf_tx = n_websocket_receive_entries > 0;
  for(int i=0; i<n_websocket_receive_entries; i++)
      rf_transmit(websocket_receive_entries[i].buffer, websocket_receive_entries[i].n);
  n_websocket_receive_entries = 0;
  lck.unlock();

  if (any_rf_tx)
    start_rf_receive();
}
