// -------------------------------------------------------------------------------------------
// Basic Master
// -------------------------------------------------------------------------------------------

#include <i2c_t3.h>

// Memory
#define MEM_LEN 256
char databuf[MEM_LEN];
int count;

void setup()
{
//    pinMode(LED_BUILTIN,OUTPUT);    // LED
//    digitalWrite(LED_BUILTIN,LOW);  // LED off
//    pinMode(12,INPUT_PULLUP);       // Control for Send
//    pinMode(11,INPUT_PULLUP);       // Control for Receive

    // Setup for Master mode, pins 37/38, external pullups, 400kHz, 200ms default timeout
    Wire1.begin(I2C_MASTER, 0x00, I2C_PINS_37_38, I2C_PULLUP_EXT, 400000);
    Wire1.setDefaultTimeout(200000); // 200ms

    // Data init
    memset(databuf, 0, sizeof(databuf));


    Serial.begin(115200);
}

void loop()
{
    uint8_t target = 0x66; // target Slave address
 
    // Send string to Slave
    if(true)
    {

        // Transmit to Slave
        Wire1.beginTransmission(target);   // Slave address
        Wire1.write("/hello;"); // Write string to I2C Tx buffer (incl. string null at end)
        Wire1.endTransmission();           // Transmit to Slave

        // Check if error occured
        if(Wire1.getError())
            Serial.print("FAIL\n");
        else
            Serial.print("OK\n");

        delay(1500);                       // Delay to space out tests
    }

    // Read string from Slave
    //
    if(true)
    {
        
        // Print message
        Serial.print("Reading from Slave: ");
        
        // Read from Slave
        Wire1.requestFrom(target, (size_t)MEM_LEN); // Read from Slave (string len unknown, request full buffer)

        // Check if error occured
        if(Wire1.getError())
            Serial.print("FAIL\n");
        else
        {
            // If no error then read Rx data into buffer and print
            Wire1.read(databuf, Wire1.available());
            Serial.printf("'%s' OK\n",databuf);
        }
        delay(100);                       // Delay to space out tests
    }
}
