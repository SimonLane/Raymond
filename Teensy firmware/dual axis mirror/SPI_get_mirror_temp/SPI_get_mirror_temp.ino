

// include the SPI library:
#include <SPI.h>


// set pin 10 as the slave select for the digital pot:
const int slaveSelectPin = 10;
const int slaveReadyPin = 35;

void setup() {
  Serial.begin(115200);
  pinMode (slaveSelectPin, OUTPUT);
  pinMode (13, OUTPUT);
  pinMode (slaveReadyPin, INPUT);
  digitalWrite (slaveSelectPin, HIGH);
  SPI.begin(); 
  delay(1000);
}

void loop() {
  delay(500);

  //sendReadSPI(0x1000);       //request Firmware ID
  //sendReadSPI(0x2200);       //request temp of actuator
  sendReadSPI(0x2201);       //request temp of proxy board
  
  Serial.println("");
}

uint8_t data;

void sendReadSPI(uint32_t Register){
  while(digitalRead(slaveReadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
  SPI.transfer(0x00);SPI.transfer(0x00);     //read command
  SPI.transfer((Register >> 8) & 0xFF);      //register to read from byte 1
  SPI.transfer((Register) & 0xFF);           //register to read from byte 2
  for(int i=0;i<10;i++){
    data = SPI.transfer(0x00);               //send blank data bytes to fill the rest of the frame
    Serial.print(data);Serial.print("\t");
    //if(i==1){Serial.print(data);Serial.print("\t");}
  }
  
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
}
