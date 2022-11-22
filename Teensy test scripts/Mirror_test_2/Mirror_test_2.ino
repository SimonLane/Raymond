#include <SPI.h>

long unsigned prev_t    = 0;

const int slaveSelectPin = 10;
const int DNreadyPin = 35;
int TriggerPin = 34;

uint32_t generateSPFPR(float f) {
  float normalized;
  int16_t shift;
  int32_t sign, exponent, significand;
 
  if (f == 0.0){return 0;} //handle this special case
                          //check sign and begin normalization
  if (f < 0) { sign = 1; normalized = -f; } 
  else { sign = 0; normalized = f; }
                          //get normalized form of f and track the exponent
  shift = 0;
  while (normalized >= 2.0) { normalized /= 2.0; shift++; }
  while (normalized < 1.0)  { normalized *= 2.0; shift--; }
  normalized = normalized - 1.0;
                          //calculate binary form (non-float) of significand 
  significand = normalized*(0x800000 + 0.5f);
                          //get biased exponent
  exponent = shift + 0x7f; //shift + bias
                          //combine and return
  return (sign<<31) | (exponent<<23) | significand;
}

void mirrorTo(float pY, float pZ){
  // -1.0 -- 1.0 range
  //conditioning to make sure Y,Z are in range
  Serial.print("move command -->");Serial.print(pY);Serial.print(" ");Serial.println(pZ);
  Serial.print("output -->");Serial.print(generateSPFPR(pY));Serial.print(" ");Serial.println(generateSPFPR(pZ));
  
  sendWriteSPI(0x50025102,generateSPFPR(pY),generateSPFPR(pZ));
}

void sendWriteSPI(uint32_t registers, uint32_t valueX, uint32_t valueY){   // quick function to write 'standard' format commands to the mirror

  //while(digitalRead(DNreadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
                           SPI.transfer(0x00);SPI.transfer(0x01);       //write command
  for(int i=24;i>-8;i=i-8){SPI.transfer((registers >> i) & 0xFF);}      //registers
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueX >> i) & 0xFF);}         //X command
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueY >> i) & 0xFF);}         //Y command
  SPI.transfer(0x7e); //delimiter byte
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
  
}
void setup() {
  Serial.begin(115200);
  pinMode(slaveSelectPin,OUTPUT);
  pinMode(DNreadyPin,INPUT);
  pinMode(TriggerPin,OUTPUT);
  delay(300);
}
float y = 0.0;
void loop() {
  if(millis() > prev_t + 100){
  prev_t = millis();
  y = y + 10.0;
  if(y > 1000){y=-1000.0;}
  mirrorTo(y/1000.0,0.0);
  }
}
