#include <SPI.h>

//SPI
bool verbose = false;
int ResetPin = 33;
int SyncPin  = 34;
int LatchPin = 35;

void setup() {
  pinMode(ResetPin,OUTPUT);
  pinMode(SyncPin, OUTPUT);
  pinMode(LatchPin,OUTPUT);
  digitalWrite(SyncPin, 1);
  digitalWrite(LatchPin,0);
  digitalWrite(ResetPin,1);
  SPI.begin();

  pinMode(31,OUTPUT);
  pinMode(30,OUTPUT);
  pinMode(29,OUTPUT);
  
  

  Serial.begin(115200);
  delay(10);
}


void setChannel(int channel, int value){
  digitalWrite(SyncPin, 0);
  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE1));
  SPI.transfer(0x30 + channel);
  SPI.transfer(value >> 8);
  SPI.transfer(value & 0xFF);
  SPI.endTransaction();
  digitalWrite(SyncPin, 1);
  if(verbose){
    Serial.println(0x30 + channel, BIN);
    Serial.println(value >> 8, BIN);
    Serial.println(value & 0xFF, BIN);
  }
}


int value = 0;
int d = 15;
void loop() {

  setChannel(9,65000);

  digitalWrite(29,1);
  setChannel(11,65000);
  setChannel(14,65000);
  setChannel(15,65000);
  delay(300);
  
  digitalWrite(29,0);
  setChannel(11,0);
  setChannel(14,0);
  setChannel(15,0);
  delay(300);
}
