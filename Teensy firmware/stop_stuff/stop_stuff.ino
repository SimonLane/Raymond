#include <SPI.h>
#include <i2c_t3.h>

#define MEM_LEN 256
char databuf[MEM_LEN];

const int slaveSelectPin = 10;
const int slaveReadyPin = 35;
const int trigger_pin_SM = 34; //trigger pin for scan mirror
const int trigger_pin_IB = 36; //trigger pin for illumination board
uint8_t data;
uint8_t target = 0x66;        //I2C address for illumination board


void setup() {
  //I2C
  Wire1.begin(I2C_MASTER, 0x00, I2C_PINS_37_38, I2C_PULLUP_EXT, 400000);
  Wire1.setDefaultTimeout(200000);            // 200ms
  memset(databuf, 0, sizeof(databuf));        //incoming I2C data buffer
  
  Serial.begin(115200);
  pinMode (slaveSelectPin, OUTPUT);
  pinMode (2, OUTPUT);
  pinMode (13, OUTPUT);
  pinMode (slaveReadyPin, INPUT);
  pinMode (trigger_pin_SM, OUTPUT);
  pinMode (trigger_pin_IB, OUTPUT);
  digitalWrite (slaveSelectPin, HIGH);
  SPI.begin(); 
  delay(1000);

//INPUT stage
  
  sendWriteSPI(0x60006100,0x02,0x02);                     //Configure both axes signal unit (02: XY units; 01: OF units; 00: current) OF = optical feedback
  sendWriteSPI(0x60096109,0x00,0x00);                     //external trigger OFF
  sendWriteSPI(0x60016101,0x00,0x00);                     //Set run flag, both axes OFF
  sendWriteSPI(0x50025102,generateSPFPR(0.5),generateSPFPR(0));       //set mirror to centre position

//CONDITIONING stage  
  sendWriteSPI(0x98009801,generateSPFPR(0.075),generateSPFPR(-0.008));      // X  (Gain, Offset), X uses only +ve side and 
                                                                           // is wider than FOV:                           FOV[+0.2 to +0.8]
  sendWriteSPI(0x99009901,generateSPFPR(0.025),generateSPFPR(0.045));      // Y  (Gain, Offset), Y is symetrical and full 
                                                                           // height of FOV:                               FOV[-1 to +1]
//CONTROL stage  
  sendWriteSPI(0x40024007,0xC0,0xC0);       //Activate closed loop control for both axes

digitalWrite(trigger_pin_SM,0);
digitalWrite(trigger_pin_IB,0);   //Triggers off

//lasers off
Wire1.write("/stop;");

}

void loop() {
  // put your main code here, to run repeatedly:

}

void sendWriteSPI(uint32_t registers, uint32_t valueX, uint32_t valueY){

  while(digitalRead(slaveReadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
                           SPI.transfer(0x00);SPI.transfer(0x01);       //write command
  for(int i=24;i>-8;i=i-8){SPI.transfer((registers >> i) & 0xFF);}      //registers
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueX >> i) & 0xFF);}         //X command
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueY >> i) & 0xFF);}         //Y command
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
  
}

void sendReadSPI(uint32_t Register){
  while(digitalRead(slaveReadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
  SPI.transfer(0x00);SPI.transfer(0x00);     //read command
  SPI.transfer((Register >> 8) & 0xFF);      //register to read from byte 1
  SPI.transfer((Register) & 0xFF);           //register to read from byte 2
  for(int i=0;i<10;i++){
    data = SPI.transfer(0x00);               //send blank data bytes to fill the rest of the frame
    if(i==1){Serial.print(data);Serial.print("\t");}
  }
  
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
}


uint32_t generateSPFPR(float f) {
  float normalized;
  int16_t shift;
  int32_t sign, exponent, significand;
 
  if (f == 0.0) 
    return 0; //handle this special case
  //check sign and begin normalization
  if (f < 0) { 
    sign = 1; 
    normalized = -f; 
  } else { 
    sign = 0; 
    normalized = f; 
  }
  //get normalized form of f and track the exponent
  shift = 0;
  while (normalized >= 2.0) { 
    normalized /= 2.0; 
    shift++; 
  }
  while (normalized < 1.0) { 
    normalized *= 2.0; 
    shift--; 
  }
  normalized = normalized - 1.0;
  //calculate binary form (non-float) of significand 
  significand = normalized*(0x800000 + 0.5f);
  //get biased exponent
  exponent = shift + 0x7f; //shift + bias
  //combine and return
  return (sign<<31) | (exponent<<23) | significand;
}
