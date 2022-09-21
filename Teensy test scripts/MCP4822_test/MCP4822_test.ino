#include <SPI.h>

int CS = 10;
int Latch = 32;

void setup() {
  Serial.begin(115200);
  pinMode(CS, OUTPUT);
  pinMode(Latch, OUTPUT);
  digitalWrite(CS,1);
  digitalWrite(Latch,1);
  SPI.begin();
  pinMode(A4,INPUT); // (for testing output)
}

void setValue(int v, int c, int g){

  byte out1 = 0x50 | (c<<7)| (g<<5) | (v>>8) ;
  byte out2 = v & 0xFF ;
  //SPI.beginTransaction(SPISettings(20000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CS, LOW);
  SPI.transfer(out1);
  SPI.transfer(out2);
  digitalWrite(CS, HIGH);
  digitalWrite(Latch,LOW);
  digitalWrite(Latch,HIGH);
}
int v = 4095;

void loop() {
  delay(5000);
  setValue(0, 0, 1);
  setValue(0, 1, 1);

    delay(5000);
  setValue(4095, 0, 1);
  setValue(4095, 1, 1);

}
